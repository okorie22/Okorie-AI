"""
Apify Lead Adapter
Maps Apify CSV fields to our database schema.
"""
import csv
import re
from typing import Dict, List, Optional, Any
from pathlib import Path
from loguru import logger


class ApifyLeadAdapter:
    """
    Adapts Apify actor outputs (CSV) to our lead database schema.
    Handles both Actor 1 and Actor 2 formats.
    """
    
    @staticmethod
    def parse_employee_size(size_str: Optional[str]) -> Optional[int]:
        """
        Parse employee size ranges into a representative integer.
        
        Examples:
            "21-50" -> 35
            "51-100" -> 75
            "10-19" -> 15
        """
        if not size_str:
            return None
        
        # Extract numbers
        match = re.search(r'(\d+)-(\d+)', str(size_str))
        if match:
            low, high = int(match.group(1)), int(match.group(2))
            return (low + high) // 2  # Average
        
        # Single number
        match = re.search(r'(\d+)', str(size_str))
        if match:
            return int(match.group(1))
        
        return None
    
    @staticmethod
    def parse_industry(industry_str: Optional[str]) -> Optional[str]:
        """
        Parse industry field, handling arrays and brackets.
        
        Examples:
            "['Legal Services']" -> "Legal Services"
            "Legal Services" -> "Legal Services"
        """
        if not industry_str:
            return None
        
        # Remove brackets and quotes
        cleaned = re.sub(r"[\[\]'\"]", "", str(industry_str))
        
        # Take first if comma-separated
        if ',' in cleaned:
            cleaned = cleaned.split(',')[0].strip()
        
        return cleaned if cleaned else None
    
    @staticmethod
    def split_name(full_name: str) -> tuple[str, str]:
        """
        Split full name into first and last name.
        
        Examples:
            "John Doe" -> ("John", "Doe")
            "John" -> ("John", "")
            "John Michael Doe" -> ("John", "Michael Doe")
        """
        if not full_name:
            return "", ""
        
        parts = full_name.strip().split()
        if len(parts) == 0:
            return "", ""
        elif len(parts) == 1:
            return parts[0], ""
        else:
            return parts[0], " ".join(parts[1:])
    
    @staticmethod
    def normalize_phone(phone: Optional[str]) -> Optional[str]:
        """
        Normalize phone number to consistent format.
        Strips all non-digit characters except leading +.
        """
        if not phone:
            return None
        
        phone_str = str(phone).strip()
        
        # Keep leading + for international
        if phone_str.startswith('+'):
            return '+' + re.sub(r'\D', '', phone_str[1:])
        
        # Remove all non-digits
        return re.sub(r'\D', '', phone_str)
    
    @staticmethod
    def normalize_email(email: Optional[str]) -> Optional[str]:
        """Normalize email to lowercase"""
        if not email:
            return None
        return str(email).strip().lower()
    
    def map_actor2_row(self, row: Dict[str, str]) -> Dict[str, Any]:
        """
        Map Actor 2 CSV row to our database schema.
        
        Actor 2 fields (from sample CSV):
            fullName, email, position, phone, linkedinUrl,
            orgName, orgWebsite, orgSize, orgIndustry,
            city, state, country
        
        Our schema fields:
            first_name, last_name, email, phone, linkedin_url,
            company_name, company_website, industry, employee_size,
            city, state, address, source
        """
        first_name, last_name = self.split_name(row.get('fullName', ''))
        
        return {
            'first_name': first_name,
            'last_name': last_name,
            'email': self.normalize_email(row.get('email')),
            'phone': self.normalize_phone(row.get('phone')),
            'linkedin_url': row.get('linkedinUrl'),
            'company_name': row.get('orgName'),
            'company_website': row.get('orgWebsite'),
            'industry': self.parse_industry(row.get('orgIndustry')),
            'employee_size': str(self.parse_employee_size(row.get('orgSize'))) if row.get('orgSize') else None,
            'job_title': row.get('position'),  # Now persisted to database
            'city': row.get('orgCity') or row.get('city'),  # Prefer orgCity (company location)
            'state': row.get('orgState') or row.get('state'),  # Prefer orgState
            'address': None,  # Not provided in Actor 2
            'zipcode': None,  # Not provided in Actor 2
            'source': 'apify_actor2',
            'consent_email': True,  # B2B cold email (check compliance)
            'consent_sms': False,  # No SMS consent from scraping
            'metadata': {
                'position': row.get('position'),
                'country': row.get('country'),
                'raw_org_size': row.get('orgSize'),
                'raw_org_industry': row.get('orgIndustry')
            }
        }
    
    def map_actor1_row(self, row: Dict[str, str]) -> Dict[str, Any]:
        """
        Map Actor 1 CSV row to our database schema.
        
        Actor 1 fields vary but typically include:
            name, email, title, company, website, phone, location, etc.
        
        Adjust mapping based on actual Actor 1 output format.
        """
        # Actor 1 format is less standardized - adjust as needed
        full_name = row.get('name', row.get('fullName', ''))
        first_name, last_name = self.split_name(full_name)
        
        # Location parsing (e.g., "Austin, TX")
        location = row.get('location', '')
        city, state = None, None
        if location and ',' in location:
            parts = location.split(',')
            city = parts[0].strip()
            state = parts[1].strip() if len(parts) > 1 else None
        
        return {
            'first_name': first_name,
            'last_name': last_name,
            'email': self.normalize_email(row.get('email')),
            'phone': self.normalize_phone(row.get('phone')),
            'linkedin_url': row.get('linkedin', row.get('linkedinUrl')),
            'company_name': row.get('company', row.get('companyName')),
            'company_website': row.get('website', row.get('companyWebsite')),
            'industry': row.get('industry'),
            'employee_size': row.get('employeeSize', row.get('companySize')),
            'city': city,
            'state': state,
            'address': row.get('address'),
            'zipcode': None,
            'source': 'apify_actor1',
            'consent_email': True,
            'consent_sms': False,
            'metadata': {
                'title': row.get('title', row.get('position')),
                'location': location
            }
        }
    
    def load_csv(self, csv_path: Path, actor_id: str) -> List[Dict[str, Any]]:
        """
        Load and map CSV file to lead records.
        
        Args:
            csv_path: Path to CSV file
            actor_id: Which actor produced this CSV
        
        Returns:
            List of normalized lead dictionaries
        """
        logger.info(f"Loading CSV from {csv_path} for actor {actor_id}")
        
        leads = []
        errors = 0
        
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for idx, row in enumerate(reader, start=1):
                    try:
                        # Determine mapping function based on actor
                        if "pipelinelabs" in actor_id or "actor2" in actor_id.lower():
                            lead = self.map_actor2_row(row)
                        else:
                            lead = self.map_actor1_row(row)
                        
                        # Validate required fields
                        if not lead.get('email'):
                            logger.debug(f"Row {idx}: Skipping - no email")
                            continue
                        
                        if not lead.get('company_name'):
                            logger.debug(f"Row {idx}: Skipping - no company")
                            continue
                        
                        # STRICT: Only accept United States leads
                        country = lead.get('metadata', {}).get('country', '').strip()
                        if country and country.lower() not in ['united states', 'usa', 'us', '']:
                            logger.debug(f"Row {idx}: Skipping - non-US country: {country}")
                            continue
                        
                        leads.append(lead)
                    
                    except Exception as e:
                        errors += 1
                        logger.warning(f"Row {idx}: Error mapping - {e}")
            
            logger.info(f"Loaded {len(leads)} valid leads from CSV ({errors} errors)")
            return leads
        
        except Exception as e:
            logger.error(f"Failed to load CSV {csv_path}: {e}")
            raise
    
    def deduplicate_by_email(self, leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove duplicate leads by email address.
        Keeps first occurrence.
        """
        seen_emails = set()
        unique_leads = []
        
        for lead in leads:
            email = lead.get('email', '').lower()
            if email and email not in seen_emails:
                seen_emails.add(email)
                unique_leads.append(lead)
        
        duplicates = len(leads) - len(unique_leads)
        if duplicates > 0:
            logger.info(f"Removed {duplicates} duplicate emails")
        
        return unique_leads
    
    def process_csv(self, csv_path: Path, actor_id: str, deduplicate: bool = True) -> List[Dict[str, Any]]:
        """
        Complete processing pipeline: load, map, deduplicate.
        
        Args:
            csv_path: Path to CSV
            actor_id: Actor that produced the CSV
            deduplicate: Whether to deduplicate by email
        
        Returns:
            List of processed lead dictionaries
        """
        leads = self.load_csv(csv_path, actor_id)
        
        if deduplicate:
            leads = self.deduplicate_by_email(leads)
        
        return leads
