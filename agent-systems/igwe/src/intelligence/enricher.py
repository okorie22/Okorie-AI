"""
Lead enrichment worker - adapted from Lead_Pipeline/enrich_leads.py
Adds website scraping with domain-level caching to avoid repeated scrapes.
"""
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional, Dict
from urllib.parse import urlparse
from loguru import logger
import requests
from bs4 import BeautifulSoup
import re

from ..storage.models import Lead, LeadEnrichment
from ..storage.repositories import EventRepository


def extract_domain(url: str) -> Optional[str]:
    """Extract domain from URL"""
    try:
        parsed = urlparse(url if url.startswith('http') else f'https://{url}')
        return parsed.netloc
    except:
        return None


def extract_simple_content(url: str, timeout: int = 10) -> str:
    """
    Simplified content extraction using requests + BeautifulSoup.
    No headless browser to avoid resource intensity.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=timeout, verify=False)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script, style, nav, header, footer
        for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
            element.decompose()
        
        # Try to find main content containers
        content_containers = soup.select('main, article, [role="main"], .content, #content, .post, .entry')
        if content_containers:
            main_content = max(content_containers, key=lambda x: len(x.get_text(strip=True)))
            text = main_content.get_text('\n', strip=True)
        else:
            text = soup.body.get_text('\n', strip=True) if soup.body else ""
        
        # Clean text
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\[.*?\]', '', text)
        text = text.strip()
        
        return text[:5000]  # Limit to 5000 chars
    
    except Exception as e:
        logger.warning(f"Error extracting content from {url}: {e}")
        return ""


def generate_simple_summary(content: str, company_name: str) -> str:
    """
    Generate a simple summary by extracting key sentences.
    Fallback if LLM is not available or too expensive to run on all leads.
    """
    if not content or len(content) < 100:
        return "No substantial content available."
    
    # Split into sentences (simple approach)
    sentences = re.split(r'(?<=[.!?])\s+', content)
    
    if len(sentences) <= 3:
        return content[:500]
    
    # Take first 2 sentences and last sentence
    summary_parts = sentences[:2] + [sentences[-1]]
    summary = " ".join(summary_parts)
    
    return summary[:500] if len(summary) > 500 else summary


def generate_personalization_bullets(content: str, lead: Lead) -> list:
    """
    Generate personalization bullets from content.
    These are quick facts for message templates.
    """
    bullets = []
    
    if lead.industry:
        bullets.append(f"Industry: {lead.industry}")
    
    if lead.employee_size:
        bullets.append(f"Team size: ~{lead.employee_size} employees")
    
    if lead.founded_year:
        age = datetime.now().year - lead.founded_year
        bullets.append(f"Established {lead.founded_year} ({age} years)")
    
    # Extract key phrases from content
    keywords = ['mission', 'specialize', 'provide', 'offer', 'serve', 'help']
    for keyword in keywords:
        pattern = f"(?i)(?:we |they )?{keyword}[^.!?]*[.!?]"
        matches = re.findall(pattern, content)
        if matches:
            bullets.append(matches[0].strip()[:100])
            break
    
    return bullets[:4]  # Max 4 bullets


class LeadEnricher:
    """Enrich leads with website content and personalization data"""
    
    def __init__(self, db: Session):
        self.db = db
        self.event_repo = EventRepository(db)
        self.cache_days = 30  # Cache domain enrichment for 30 days
    
    def check_cache(self, domain: str) -> Optional[LeadEnrichment]:
        """
        Check if we have recent enrichment data for this domain.
        Returns cached enrichment if found within cache_days.
        """
        cutoff_date = datetime.utcnow() - timedelta(days=self.cache_days)
        
        cached = self.db.query(LeadEnrichment).filter(
            LeadEnrichment.company_domain == domain,
            LeadEnrichment.enriched_at >= cutoff_date
        ).first()
        
        return cached
    
    def enrich_lead(self, lead: Lead, force: bool = False) -> Optional[LeadEnrichment]:
        """
        Enrich a single lead with website data.
        Uses domain-level caching to avoid repeated scrapes.
        """
        logger.info(f"Enriching lead: {lead.first_name} {lead.last_name} (ID: {lead.id})")
        
        # Check if already enriched
        existing = self.db.query(LeadEnrichment).filter(
            LeadEnrichment.lead_id == lead.id
        ).first()
        
        if existing and not force:
            logger.info(f"Lead {lead.id} already enriched")
            return existing
        
        # Check website URL
        if not lead.company_website:
            logger.warning(f"Lead {lead.id} has no website URL")
            return None
        
        # Extract domain for caching
        domain = extract_domain(lead.company_website)
        if not domain:
            logger.warning(f"Invalid website URL: {lead.company_website}")
            return None
        
        # Check cache
        if not force:
            cached = self.check_cache(domain)
            if cached and cached.lead_id != lead.id:
                logger.info(f"Using cached enrichment for domain: {domain}")
                
                # Create enrichment record for this lead using cached data
                enrichment = LeadEnrichment(
                    lead_id=lead.id,
                    company_domain=domain,
                    website_summary=cached.website_summary,
                    personalization_bullets=generate_personalization_bullets(
                        cached.website_summary or "", lead
                    ),
                    confidence_score=cached.confidence_score
                )
                self.db.add(enrichment)
                self.db.commit()
                self.db.refresh(enrichment)
                
                self.event_repo.log(
                    event_type="lead_enriched",
                    lead_id=lead.id,
                    payload={"method": "cache", "domain": domain}
                )
                
                return enrichment
        
        # Scrape website (simplified approach)
        try:
            logger.info(f"Scraping website: {lead.company_website}")
            content = extract_simple_content(lead.company_website)
            
            if not content or len(content) < 100:
                logger.warning(f"Insufficient content extracted from {lead.company_website}")
                confidence = 0
                summary = "No meaningful content could be extracted."
                bullets = []
            else:
                confidence = min(100, len(content) // 50)  # Simple confidence metric
                summary = generate_simple_summary(content, lead.company_name or "")
                bullets = generate_personalization_bullets(content, lead)
            
            # Create or update enrichment
            if existing:
                existing.company_domain = domain
                existing.website_summary = summary
                existing.personalization_bullets = bullets
                existing.confidence_score = confidence
                existing.enriched_at = datetime.utcnow()
                self.db.commit()
                self.db.refresh(existing)
                enrichment = existing
            else:
                enrichment = LeadEnrichment(
                    lead_id=lead.id,
                    company_domain=domain,
                    website_summary=summary,
                    personalization_bullets=bullets,
                    confidence_score=confidence
                )
                self.db.add(enrichment)
                self.db.commit()
                self.db.refresh(enrichment)
            
            # Log event
            self.event_repo.log(
                event_type="lead_enriched",
                lead_id=lead.id,
                payload={
                    "method": "scrape",
                    "domain": domain,
                    "confidence": confidence
                }
            )
            
            logger.success(f"Lead {lead.id} enriched successfully")
            return enrichment
        
        except Exception as e:
            logger.error(f"Error enriching lead {lead.id}: {e}")
            return None
    
    def enrich_high_priority_leads(self, tier_threshold: int = 2) -> Dict:
        """
        Enrich only high-priority leads (tier 1-2) that don't have enrichment.
        """
        from ..storage.models import LeadScore
        
        # Find high-tier leads without enrichment
        leads = self.db.query(Lead).join(LeadScore).outerjoin(LeadEnrichment).filter(
            LeadScore.tier <= tier_threshold,
            LeadEnrichment.id == None,
            Lead.company_website != None
        ).all()
        
        logger.info(f"Found {len(leads)} high-priority leads to enrich")
        
        enriched = 0
        skipped = 0
        errors = 0
        
        for lead in leads:
            try:
                result = self.enrich_lead(lead)
                if result:
                    enriched += 1
                else:
                    skipped += 1
            except Exception as e:
                errors += 1
                logger.error(f"Error enriching lead {lead.id}: {e}")
        
        return {"enriched": enriched, "skipped": skipped, "errors": errors}
