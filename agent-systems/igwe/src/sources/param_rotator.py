"""
Search parameter rotation for Apify actor runs.
Systematically varies search parameters to diversify lead pool.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from itertools import product
from loguru import logger
import hashlib
import json


class ParamRotator:
    """
    Generates and tracks search parameter combinations to ensure variety.
    Now loads parameters from config for easy customization.
    """
    
    def __init__(self, db_session=None, config=None):
        """
        Args:
            db_session: Optional SQLAlchemy session to track used combos
            config: Optional ApifyConfig instance (will load from default if not provided)
        """
        self.db_session = db_session
        
        # Load parameters from config
        if config is None:
            from ..config import apify_config
            config = apify_config
        
        self.INDUSTRIES = config.industries_list
        self.STATES = config.states_list
        self.SIZES = config.sizes_list
        self.TITLES = config.titles_list
    
    @staticmethod
    def generate_param_hash(params: Dict[str, Any]) -> str:
        """Generate deterministic hash for parameter set"""
        # Sort keys to ensure consistent hashing
        param_str = json.dumps(params, sort_keys=True)
        return hashlib.md5(param_str.encode()).hexdigest()
    
    def get_next_params_actor1(
        self,
        used_hashes: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Get next parameter set for Actor 1 (code_crafter~leads-finder).
        
        Args:
            used_hashes: List of parameter hashes already used
        
        Returns:
            Dict of parameters for the actor
        """
        if used_hashes is None:
            used_hashes = []
        
        # Generate all possible combinations
        combinations = []
        for industry, state, title in product(self.INDUSTRIES, self.STATES, self.TITLES):
            search_term = f"{industry} {title.lower()}"
            params = {
                "searchTerm": search_term,
                "location": state,
                "maxResults": 100
            }
            param_hash = self.generate_param_hash(params)
            
            if param_hash not in used_hashes:
                combinations.append((params, param_hash))
        
        if not combinations:
            logger.warning("All Actor 1 parameter combinations exhausted. Resetting rotation.")
            # Start over - return first combo
            industry, state, title = self.INDUSTRIES[0], self.STATES[0], self.TITLES[0]
            search_term = f"{industry} {title.lower()}"
            params = {
                "searchTerm": search_term,
                "location": state,
                "maxResults": 100
            }
            return params
        
        # Return first unused combination
        params, param_hash = combinations[0]
        logger.info(f"Generated Actor 1 params: {params['searchTerm']} in {params['location']}")
        return params
    
    def get_next_params_actor2(
        self,
        used_hashes: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Get next parameter set for Actor 2 (pipelinelabs~lead-scraper-apollo-zoominfo-lusha-ppe).
        
        Rotation Strategy: MAXIMUM INDUSTRY + STATE DIVERSITY
        
        Phase 1 (First 100 runs): ONE combination per industry+state pair
        - Uses default size (51-100) and default title (Owner)
        - Ensures you test ALL 100 market combinations (10 industries × 10 states) quickly
        
        Phase 2 (Subsequent runs): Fill in remaining size/title variations
        - Goes back through and adds different sizes and titles
        - Completes full coverage of all 3,500 possible combinations
        
        Example rotation sequence:
        1. Law Practice, Texas, 51-100, (default)
        2. Law Practice, Florida, 51-100, (default)
        3. Law Practice, California, 51-100, (default)
        ...
        10. Law Practice, Colorado, 51-100, (default) [all states for Law Practice]
        11. Accounting, Texas, 51-100, (default) [next industry]
        ...
        100. Architecture & Planning, Colorado, 51-100, (default) [all industry+state combos covered]
        101. Law Practice, Texas, 11-20, Owner [Phase 2: start filling variations]
        102. Law Practice, Texas, 21-50, Owner
        ...
        
        Uses current parameter format:
        - personLocationCountryIncludes (fixed to ["United States"])
        - personLocationStateIncludes (state names only)
        - companyIndustryIncludes (industry names)
        - companyEmployeeSizeIncludes (size ranges)
        - includeSimilarTitles (boolean)
        
        Args:
            used_hashes: List of parameter hashes already used
        
        Returns:
            Dict of parameters for the actor
        """
        if used_hashes is None:
            used_hashes = []
        
        # AGGRESSIVE DIVERSITY STRATEGY:
        # Generate ONE combination per industry+state pair initially
        # Use middle-range size (51-100) and first title (Owner) as defaults
        # This maximizes industry+state variety in first 100 runs
        
        combinations = []
        default_size = "51-100"  # Middle range
        default_title = self.TITLES[0] if self.TITLES else "Owner"
        
        # First pass: One combo per industry+state (100 combinations for quick market coverage)
        for industry, state in product(self.INDUSTRIES, self.STATES):
            params = {
                "personLocationCountryIncludes": ["United States"],
                "personLocationStateIncludes": [state],
                "companyIndustryIncludes": [industry],
                "companyEmployeeSizeIncludes": [default_size],
                "includeSimilarTitles": False,
                "emailStatus": "verified",
                "hasEmail": True,
                "hasPhone": False,
                "resetSavedProgress": False,
                "totalResults": 100
            }
            param_hash = self.generate_param_hash(params)
            
            if param_hash not in used_hashes:
                combinations.append((params, param_hash))
        
        # Second pass: Fill in remaining size/title variations
        # Only runs after we've covered all industry+state pairs once
        if not combinations:
            for industry, state in product(self.INDUSTRIES, self.STATES):
                for size, title in product(self.SIZES, self.TITLES):
                    # Skip the default combo we already used in first pass
                    if size == default_size and title == default_title:
                        continue
                        
                    params = {
                        "personLocationCountryIncludes": ["United States"],
                        "personLocationStateIncludes": [state],
                        "companyIndustryIncludes": [industry],
                        "companyEmployeeSizeIncludes": [size],
                        "includeSimilarTitles": False,
                        "emailStatus": "verified",
                        "hasEmail": True,
                        "hasPhone": False,
                        "resetSavedProgress": False,
                        "totalResults": 100
                    }
                    param_hash = self.generate_param_hash(params)
                    
                    if param_hash not in used_hashes:
                        combinations.append((params, param_hash))
        
        if not combinations:
            logger.warning("All Actor 2 parameter combinations exhausted. Resetting rotation.")
            # Return default params
            params = {
                "personLocationCountryIncludes": ["United States"],
                "personLocationStateIncludes": [self.STATES[0]],
                "companyIndustryIncludes": [self.INDUSTRIES[0]],
                "companyEmployeeSizeIncludes": [self.SIZES[0]],
                "includeSimilarTitles": False,
                "emailStatus": "verified",
                "hasEmail": True,
                "hasPhone": False,
                "resetSavedProgress": False,
                "totalResults": 100
            }
            return params
        
        # Return first unused combination
        params, param_hash = combinations[0]
        logger.info(f"Generated Actor 2 params: {params['companyIndustryIncludes'][0]}, {params['companyEmployeeSizeIncludes'][0]} employees in {params['personLocationStateIncludes'][0]}")
        return params
    
    def get_next_params(
        self,
        actor_id: str,
        used_hashes: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Get next params for any actor.
        
        Args:
            actor_id: The Apify actor ID
            used_hashes: List of parameter hashes already used
        
        Returns:
            Dict of parameters
        """
        if "code_crafter" in actor_id or "leads-finder" in actor_id:
            return self.get_next_params_actor1(used_hashes)
        elif "pipelinelabs" in actor_id or "lead-scraper" in actor_id:
            return self.get_next_params_actor2(used_hashes)
        else:
            raise ValueError(f"Unknown actor: {actor_id}")
    
    def get_used_param_hashes(self, actor_id: str, limit: int = 100) -> List[str]:
        """
        Get list of recently used parameter hashes from database.
        
        Args:
            actor_id: Filter by actor
            limit: Max number of recent hashes to return
        
        Returns:
            List of parameter hashes
        """
        if not self.db_session:
            return []
        
        try:
            from ..storage.models import LeadSourceRun
            
            runs = (
                self.db_session.query(LeadSourceRun)
                .filter(LeadSourceRun.actor_name == actor_id)
                .order_by(LeadSourceRun.started_at.desc())
                .limit(limit)
                .all()
            )
            
            return [run.params_hash for run in runs if run.params_hash]
        
        except Exception as e:
            logger.warning(f"Could not fetch used param hashes: {e}")
            return []
    
    def create_custom_params(
        self,
        actor_id: str,
        industry: Optional[str] = None,
        state: Optional[str] = None,
        size: Optional[str] = None,
        title: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create custom parameter set with manual overrides.
        
        Args:
            actor_id: Actor to generate params for
            industry: Optional industry override
            state: Optional state override
            size: Optional size override
            title: Optional title override
        
        Returns:
            Dict of parameters
        """
        # Use defaults from class constants
        industry = industry or self.INDUSTRIES[0]
        state = state or self.STATES[0]
        size = size or self.SIZES[1]  # Default to 20-50
        title = title or self.TITLES[0]
        
        if "code_crafter" in actor_id or "leads-finder" in actor_id:
            search_term = f"{industry} {title.lower()}"
            return {
                "searchTerm": search_term,
                "location": state,
                "maxResults": 100
            }
        else:
            # Actor 2 format
            industry_tags = {
                "law": "5567cd4773696439b10b23ba",
                "accounting": "5567cd4773696439b10b23bb",
                "medical": "5567cd4773696439b10b23bc",
                "consulting": "5567cd4773696439b10b23bd",
                "financial_services": "5567cd4773696439b10b23be"
            }
            
            return {
                "personTitles": [title],
                "organizationIndustryTagIds": [industry_tags.get(industry, industry_tags["law"])],
                "organizationNumEmployeesRanges": [size],
                "personLocations": [state],
                "contactEmailStatus": ["verified"],
                "page": 1,
                "perPage": 100
            }
