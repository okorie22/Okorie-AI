"""
Lead normalization and ingestion - adapted from Lead_Pipeline/process_leads.py
Converts raw lead data from various sources into standardized database records.
"""
import pandas as pd
from sqlalchemy.orm import Session
from typing import Dict, List, Optional
from loguru import logger

from ..storage.models import Lead, LeadSource
from ..storage.repositories import LeadRepository, EventRepository


# Field mappings from Lead_Pipeline (reused verbatim)
FIELD_MAPPINGS = {
    # Apollo-io-scraper format
    "apollo-io-scraper": {
        "first_name": ["first_name", "given_name", "firstName"],
        "last_name": ["last_name", "surname", "lastName"],
        "email": ["email", "email_address", "emailAddress"],
        "personal_linkedin": ["linkedin_url", "personLinkedInUrl", "linkedInProfileUrl"],
        "company_name": ["organization/name", "name", "organization_name", "organization/organization_name"],
        "company_phone": ["organization/primary_phone/number", "organization/phone", "phone", "personal_phone", "phoneNumber", "contactPhoneNumbers/0/rawNumber"],
        "website_url": ["organization/website_url"],
        "industry": ["organization/industry", "organization/industries/0"],
        "employee_size": ["organization/estimated_num_employees"],
        "founded_year": ["organization/founded_year"],
        "address": ["organization/street_address", "organization/address", "address"],
        "city": ["organization/city", "organization/locality", "locality"],
        "state": ["organization/state"],
        "zipcode": ["organization/postal_code", "organization/zip", "organization/zip_code", "zip", "zip_code"]
    },
    
    # Apollo-scraper format
    "apollo-scraper": {
        "first_name": ["firstName"],
        "last_name": ["lastName"],
        "email": ["emailAddress", "email"],
        "personal_linkedin": ["linkedInProfileUrl", "personal_linkedin", "linkedin_url"],
        "company_name": ["company/companyName", "companyName", "organization/name", "organization_name"],
        "company_phone": ["company/mainPhone/phoneNumber", "company/cleanedPhoneNumber", "cleanedPhoneNumber", "organization/phone", "contactPhone", "company/contactPhone", "phone", "personal_phone", "phoneNumber", "contactPhoneNumbers/0/rawNumber"],
        "website_url": ["company/websiteUrl"],
        "industry": ["company/businessIndustry", "company/businessIndustries/0", "company/industry", "industry"],
        "employee_size": ["company/employeeEstimate"],
        "founded_year": ["company/yearFounded"],
        "address": ["company/addressLine", "company/address", "address", "company/streetAddress"],
        "city": ["company/cityName", "company/city", "city", "company/location/city"],
        "state": ["company/stateName"],
        "zipcode": ["company/zipCode", "company/postalCode", "company/postal_code", "postalCode", "postal_code"]
    }
}


def detect_file_format(headers: List[str]) -> str:
    """
    Detect the format of the file based on headers.
    Returns 'apollo-io-scraper' or 'apollo-scraper'
    """
    # Check for apollo-io-scraper format
    io_scraper_indicators = ["organization/name", "organization/", "first_name"]
    for indicator in io_scraper_indicators:
        if any(indicator in h for h in headers):
            return "apollo-io-scraper"
    
    # Check for apollo-scraper format
    scraper_indicators = ["company/companyName", "company/", "firstName"]
    for indicator in scraper_indicators:
        if any(indicator in h for h in headers):
            return "apollo-scraper"
    
    # Default to apollo-scraper
    logger.warning("Could not definitively determine file format. Defaulting to apollo-scraper.")
    return "apollo-scraper"


def clean_value(value) -> str:
    """Clean and standardize values"""
    if value is None:
        return ""
    
    # Convert to string and strip whitespace
    value = str(value).strip()
    
    # Handle common variations of empty values
    if value.lower() in ["none", "nan", "null", "undefined", "n/a", "unknown", "-", "false"]:
        return ""
    
    # Remove leading/trailing quotes
    value = value.strip('"\'')
    
    return value


def get_value_from_mapping(row: pd.Series, field_options: List[str]) -> str:
    """
    Try to get a value from the row using multiple possible field names.
    Returns the first non-empty value found or an empty string.
    """
    for field in field_options:
        if field in row and pd.notna(row[field]) and row[field] != "":
            return clean_value(row[field])
    return ""


def normalize_lead_data(row: pd.Series, field_mapping: Dict) -> Dict:
    """
    Normalize a single lead record from CSV row to database format.
    """
    return {
        "first_name": get_value_from_mapping(row, field_mapping["first_name"]),
        "last_name": get_value_from_mapping(row, field_mapping["last_name"]),
        "email": get_value_from_mapping(row, field_mapping["email"]),
        "phone": get_value_from_mapping(row, field_mapping.get("company_phone", [])),
        "linkedin_url": get_value_from_mapping(row, field_mapping["personal_linkedin"]),
        "company_name": get_value_from_mapping(row, field_mapping["company_name"]),
        "company_website": get_value_from_mapping(row, field_mapping.get("website_url", [])),
        "industry": get_value_from_mapping(row, field_mapping["industry"]),
        "employee_size": int(get_value_from_mapping(row, field_mapping["employee_size"]) or 0) or None,
        "founded_year": int(get_value_from_mapping(row, field_mapping["founded_year"]) or 0) or None,
        "address": get_value_from_mapping(row, field_mapping.get("address", [])),
        "city": get_value_from_mapping(row, field_mapping.get("city", [])),
        "state": get_value_from_mapping(row, field_mapping.get("state", [])),
        "zipcode": get_value_from_mapping(row, field_mapping.get("zipcode", [])),
        "source": LeadSource.CSV,
        "consent_sms": False,  # Default to False for CSV imports
        "consent_email": False,  # Will be set based on source
    }


class LeadProcessor:
    """Process and import leads from CSV files"""
    
    def __init__(self, db: Session):
        self.db = db
        self.lead_repo = LeadRepository(db)
        self.event_repo = EventRepository(db)
    
    def process_csv_file(self, file_path: str, source: LeadSource = LeadSource.CSV) -> Dict:
        """
        Process a CSV file and import leads into database.
        Returns statistics about the import.
        """
        logger.info(f"Processing CSV file: {file_path}")
        
        try:
            # Read CSV with pandas
            df = pd.read_csv(file_path, low_memory=False)
            headers = df.columns.tolist()
            
            # Detect format
            file_format = detect_file_format(headers)
            field_mapping = FIELD_MAPPINGS[file_format]
            logger.info(f"Detected file format: {file_format}")
            
            # Process each row
            imported = 0
            duplicates = 0
            errors = 0
            
            for idx, row in df.iterrows():
                try:
                    # Normalize data
                    lead_data = normalize_lead_data(row, field_mapping)
                    lead_data["source"] = source
                    
                    # Skip if no name and email
                    if not lead_data["first_name"] and not lead_data["last_name"] and not lead_data["email"]:
                        logger.debug(f"Skipping row {idx}: missing required fields")
                        continue
                    
                    # Check for duplicates by email first, then phone
                    existing = self.lead_repo.find_by_email(lead_data["email"])
                    
                    if not existing and lead_data.get("phone"):
                        existing = self.lead_repo.find_by_phone(lead_data["phone"])
                    
                    if existing:
                        duplicates += 1
                        logger.debug(f"Duplicate lead found: {lead_data['email']}")
                        continue
                    
                    # Create lead
                    lead = self.lead_repo.create(lead_data)
                    imported += 1
                    
                    # Log event
                    self.event_repo.log(
                        event_type="lead_created",
                        lead_id=lead.id,
                        payload={"source": source, "file": file_path}
                    )
                    
                    if imported % 10 == 0:
                        logger.info(f"Imported {imported} leads so far...")
                
                except Exception as e:
                    errors += 1
                    logger.error(f"Error processing row {idx}: {e}")
                    continue
            
            stats = {
                "total_rows": len(df),
                "imported": imported,
                "duplicates": duplicates,
                "errors": errors
            }
            
            logger.success(f"Import completed: {imported} imported, {duplicates} duplicates, {errors} errors")
            return stats
        
        except Exception as e:
            logger.error(f"Error processing CSV file: {e}")
            raise
    
    def create_lead_from_webform(self, form_data: Dict) -> Lead:
        """
        Create a lead from web form submission.
        Web form leads have SMS/email consent by default.
        """
        lead_data = {
            "first_name": form_data.get("first_name", ""),
            "last_name": form_data.get("last_name", ""),
            "email": form_data.get("email", ""),
            "phone": form_data.get("phone", ""),
            "company_name": form_data.get("company_name", ""),
            "state": form_data.get("state", ""),
            "source": LeadSource.WEBFORM,
            "consent_sms": form_data.get("consent_sms", True),  # Opt-in forms have consent
            "consent_email": form_data.get("consent_email", True),
        }
        
        # Check for duplicates by email first, then phone
        existing = self.lead_repo.find_by_email(lead_data["email"])
        
        if not existing and lead_data.get("phone"):
            existing = self.lead_repo.find_by_phone(lead_data["phone"])
        
        if existing:
            logger.warning(f"Duplicate webform submission: {lead_data['email']}")
            return existing
        
        # Create lead
        lead = self.lead_repo.create(lead_data)
        
        # Log event
        self.event_repo.log(
            event_type="lead_created",
            lead_id=lead.id,
            payload={"source": "webform", "form_data": form_data}
        )
        
        logger.info(f"Created lead from webform: {lead.email}")
        return lead
