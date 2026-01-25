"""
Lead scoring worker - adapted from Lead_Pipeline/score_leads.py
Implements the IUL Prospect Scoring Algorithm.
"""
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Dict, Optional
from loguru import logger

from ..storage.models import Lead, LeadScore
from ..storage.repositories import LeadRepository, EventRepository


# Current year for business age calculation
CURRENT_YEAR = datetime.now().year


# Industry type scores (from scoring rules.md)
INDUSTRY_TYPE_SCORES = {
    # High-value industries (22-25 points)
    "law practice": 24,
    "legal service": 23,
    "legal services": 23,
    "accounting": 23,
    
    # Hospital & Healthcare (20-24 points)
    "hospital & health care": 22,
    "health, wellness & fitness": 21,
    "mental health care": 21,
    "medical practice": 22,
    
    # Financial Services (19-23 points)
    "financial services": 21,
    "investment management": 21,
    "insurance": 20,
    
    # Management Consulting (18-22 points)
    "management consulting": 20,
    
    # Technology-related (18-22 points)
    "information technology": 20,
    "computer software": 20,
    "computer & network security": 20,
    "internet": 19,
    
    # Construction-related (17-21 points)
    "construction": 19,
    "building materials": 19,
    "civil engineering": 19,
    "mechanical or industrial engineering": 18,
    
    # Design & Creative (16-20 points)
    "architecture & planning": 18,
    "design": 18,
    
    # Service-based (15-19 points)
    "marketing & advertising": 17,
    "electrical/electronic manufacturing": 17,
    
    # Wholesale (14-18 points)
    "wholesale": 16,
    
    # Real Estate (13-17 points)
    "real estate": 15,
    "commercial real estate": 15,
    
    # Hospitality & Food (10-14 points)
    "hospitality": 12,
    "restaurants": 12,
    "food & beverages": 12,
    
    # Retail (8-12 points)
    "retail": 10,
    
    # Agriculture & Transportation (7-11 points)
    "agriculture": 9,
    "transportation/trucking/railroad": 9,
    "logistics & supply chain": 9,
    
    # Default
    "other": 7
}


def score_employee_size(size: Optional[int]) -> int:
    """Score based on employee count"""
    if not size:
        return 2
    
    if 20 <= size <= 50:
        return 18  # Optimal size
    elif 51 <= size <= 100:
        return 16
    elif 10 <= size <= 19:
        return 14
    elif 101 <= size <= 250:
        return 12
    elif 5 <= size <= 9:
        return 10
    elif 251 <= size <= 500:
        return 8
    elif 1 <= size <= 4:
        return 6
    elif size > 500:
        return 4
    else:
        return 2


def score_business_age(founded_year: Optional[int]) -> int:
    """Score based on business age"""
    if not founded_year:
        return 5
    
    age = CURRENT_YEAR - founded_year
    
    if 3 <= age <= 7:
        return 18  # Prime window
    elif 8 <= age <= 12:
        return 15
    elif 13 <= age <= 20:
        return 12
    elif 1 <= age <= 2:
        return 9
    elif 21 <= age <= 30:
        return 7
    elif age > 30:
        return 5
    elif age < 1:
        return 3
    else:
        return 5


def score_location(state: Optional[str]) -> int:
    """Score based on state location"""
    if not state:
        return 4
    
    state = state.strip().lower()
    
    # Business-Friendly States (12-15 points)
    business_friendly_states = {
        'texas': 14, 'florida': 14, 'tennessee': 13, 'nevada': 13, 'wyoming': 13,
        'south dakota': 13, 'north dakota': 13, 'utah': 13, 'indiana': 13,
        'arizona': 13, 'alabama': 12, 'oklahoma': 12, 'kentucky': 12,
        'idaho': 12, 'mississippi': 12, 'missouri': 12, 'arkansas': 12
    }
    
    # Moderate Regulatory States (9-12 points)
    moderate_states = {
        'georgia': 11, 'north carolina': 11, 'south carolina': 11, 'ohio': 11,
        'kansas': 10, 'iowa': 10, 'nebraska': 10, 'montana': 10, 'louisiana': 10,
        'new hampshire': 10, 'virginia': 10, 'west virginia': 9, 'delaware': 9,
        'pennsylvania': 9, 'wisconsin': 9, 'michigan': 9, 'alaska': 9
    }
    
    # High-Tax/Regulatory States (6-9 points)
    high_tax_states = {
        'california': 8, 'new york': 8, 'new jersey': 7, 'illinois': 7,
        'massachusetts': 7, 'connecticut': 7, 'maryland': 7, 'rhode island': 6,
        'minnesota': 6, 'oregon': 6, 'hawaii': 6, 'vermont': 6, 'maine': 6,
        'washington': 6
    }
    
    # State-specific adjustments
    estate_tax_states = [
        'connecticut', 'hawaii', 'illinois', 'massachusetts', 'maryland', 'maine',
        'minnesota', 'new york', 'oregon', 'rhode island', 'vermont', 'washington'
    ]
    
    high_premium_tax_states = [
        'alabama', 'alaska', 'delaware', 'florida', 'hawaii', 'illinois',
        'kentucky', 'mississippi', 'new mexico', 'south dakota', 'tennessee',
        'texas', 'utah', 'west virginia', 'wyoming'
    ]
    
    strong_insurance_dept_states = ['california', 'new york', 'florida', 'illinois', 'texas']
    
    # Base score
    if state in business_friendly_states:
        score = business_friendly_states[state]
    elif state in moderate_states:
        score = moderate_states[state]
    elif state in high_tax_states:
        score = high_tax_states[state]
    else:
        score = 4
    
    # Apply adjustments
    if state in estate_tax_states:
        score += 1
    if state in high_premium_tax_states:
        score -= 1
    if state in strong_insurance_dept_states:
        score += 1
    
    # Ensure score stays within valid range (1-15)
    return max(1, min(score, 15))


def score_contact_quality(linkedin_url: Optional[str], email: Optional[str]) -> int:
    """Score based on contact quality"""
    has_linkedin = bool(linkedin_url)
    has_email = bool(email and email != "email_not_unlocked@domain.com")
    
    if has_linkedin and has_email:
        return 18  # Optimal combination
    elif has_linkedin:
        return 12  # LinkedIn only
    elif has_email:
        return 10  # Email only
    else:
        return 5  # Company phone only


def calculate_tier(score: int) -> int:
    """Calculate tier from score (1 = highest priority, 5 = lowest)"""
    if 85 <= score <= 100:
        return 1
    elif 70 <= score < 85:
        return 2
    elif 55 <= score < 70:
        return 3
    elif 40 <= score < 55:
        return 4
    else:
        return 5


class LeadScorer:
    """Score leads based on IUL prospect scoring algorithm"""
    
    def __init__(self, db: Session):
        self.db = db
        self.event_repo = EventRepository(db)
    
    def score_lead(self, lead: Lead) -> LeadScore:
        """
        Score a single lead and create/update LeadScore record.
        """
        logger.info(f"Scoring lead: {lead.first_name} {lead.last_name} (ID: {lead.id})")
        
        # Score Industry Type (25 points)
        industry = (lead.industry or "").lower()
        industry_score = 7  # Default "other" category
        for key, score in INDUSTRY_TYPE_SCORES.items():
            if key in industry:
                industry_score = score
                break
        
        # Score Employee Size (20 points)
        employee_score = score_employee_size(lead.employee_size)
        
        # Score Business Age (20 points)
        age_score = score_business_age(lead.founded_year)
        
        # Score Location (15 points)
        location_score = score_location(lead.state)
        
        # Score Contact Quality (20 points)
        contact_score = score_contact_quality(lead.linkedin_url, lead.email)
        
        # Calculate total score
        total_score = industry_score + employee_score + age_score + location_score + contact_score
        tier = calculate_tier(total_score)
        
        # Check if score exists
        existing_score = self.db.query(LeadScore).filter(LeadScore.lead_id == lead.id).first()
        
        if existing_score:
            # Update existing score
            existing_score.score = total_score
            existing_score.tier = tier
            existing_score.industry_score = industry_score
            existing_score.employee_score = employee_score
            existing_score.age_score = age_score
            existing_score.location_score = location_score
            existing_score.contact_score = contact_score
            existing_score.scored_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(existing_score)
            lead_score = existing_score
        else:
            # Create new score
            lead_score = LeadScore(
                lead_id=lead.id,
                score=total_score,
                tier=tier,
                industry_score=industry_score,
                employee_score=employee_score,
                age_score=age_score,
                location_score=location_score,
                contact_score=contact_score
            )
            self.db.add(lead_score)
            self.db.commit()
            self.db.refresh(lead_score)
        
        # Log event
        self.event_repo.log(
            event_type="lead_scored",
            lead_id=lead.id,
            payload={
                "score": total_score,
                "tier": tier,
                "breakdown": {
                    "industry": industry_score,
                    "employee": employee_score,
                    "age": age_score,
                    "location": location_score,
                    "contact": contact_score
                }
            }
        )
        
        logger.success(f"Lead scored: {total_score} points (Tier {tier})")
        return lead_score
    
    def score_all_unscored(self) -> Dict:
        """Score all leads that don't have scores yet"""
        unscored_leads = self.db.query(Lead).outerjoin(LeadScore).filter(
            LeadScore.id == None
        ).all()
        
        logger.info(f"Found {len(unscored_leads)} unscored leads")
        
        scored = 0
        errors = 0
        
        for lead in unscored_leads:
            try:
                self.score_lead(lead)
                scored += 1
            except Exception as e:
                errors += 1
                logger.error(f"Error scoring lead {lead.id}: {e}")
        
        return {"scored": scored, "errors": errors}
