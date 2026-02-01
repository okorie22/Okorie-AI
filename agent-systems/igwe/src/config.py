"""
Centralized configuration management using Pydantic settings.
All environment variables and system configuration in one place.
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List, Optional
import os
from pathlib import Path


class DatabaseConfig(BaseSettings):
    """Database configuration"""
    url: str = Field(default="sqlite:///./iul_appointment_setter.db", alias="DATABASE_URL")
    
    class Config:
        env_prefix = ""


class RedisConfig(BaseSettings):
    """Redis configuration for Celery"""
    url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    
    class Config:
        env_prefix = ""


class SendGridConfig(BaseSettings):
    """SendGrid email configuration"""
    api_key: str = Field(default="", alias="SENDGRID_API_KEY")
    from_email: str = Field(default="appointments@example.com", alias="SENDGRID_FROM_EMAIL")
    from_name: str = Field(default="Your Name", alias="SENDGRID_FROM_NAME")
    # Signature footer: company name shown under sender name in email body
    signature_company: str = Field(default="", alias="SENDGRID_SIGNATURE_COMPANY")
    # Signature style: sig_default | sig_compact | sig_full (see template_variants.EMAIL_SIGNATURE_OPTIONS)
    signature_style: str = Field(default="sig_default", alias="SENDGRID_SIGNATURE_STYLE")
    # Reply-To for inbound parse (e.g. replies@reimaginewealth.org so lead replies hit SendGrid → webhook)
    reply_to: str = Field(default="", alias="SENDGRID_REPLY_TO")
    
    # TEST MODE - Set to True to prevent actual email sends (logs only)
    test_mode: bool = Field(default=False, alias="SENDGRID_TEST_MODE")
    
    # Throttling and rate limiting
    warmup_mode: bool = Field(default=True, alias="SENDGRID_WARMUP_MODE")
    daily_send_cap: int = Field(default=50, alias="SENDGRID_DAILY_CAP")  # Starts at 50, managed by warmup
    hourly_send_cap: int = Field(default=10, alias="SENDGRID_HOURLY_CAP")
    batch_size: int = Field(default=20, alias="SENDGRID_BATCH_SIZE")  # Per dispatcher run
    
    # Send window (EST timezone)
    send_start_hour: int = Field(default=8, alias="SENDGRID_SEND_START_HOUR")  # 8 AM EST
    send_end_hour: int = Field(default=17, alias="SENDGRID_SEND_END_HOUR")  # 5 PM EST
    send_weekdays_only: bool = Field(default=True, alias="SENDGRID_WEEKDAYS_ONLY")
    
    class Config:
        env_prefix = ""


class TwilioConfig(BaseSettings):
    """Twilio SMS configuration"""
    account_sid: str = Field(default="", alias="TWILIO_ACCOUNT_SID")
    auth_token: str = Field(default="", alias="TWILIO_AUTH_TOKEN")
    phone_number: str = Field(default="", alias="TWILIO_PHONE_NUMBER")
    
    # TEST MODE - Set to True to prevent actual SMS sends (logs only)
    test_mode: bool = Field(default=False, alias="TWILIO_TEST_MODE")
    
    class Config:
        env_prefix = ""


class CalendlyConfig(BaseSettings):
    """Calendly scheduling configuration"""
    api_key: str = Field(default="", alias="CALENDLY_API_KEY")
    event_type_uuid: str = Field(default="", alias="CALENDLY_EVENT_TYPE_UUID")
    user_uri: str = Field(default="https://calendly.com/your-link", alias="CALENDLY_USER_URI")
    
    class Config:
        env_prefix = ""


class LLMConfig(BaseSettings):
    """LLM provider configuration"""
    deepseek_api_key: str = Field(default="", alias="DEEPSEEK_API_KEY")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    provider: str = Field(default="deepseek", alias="LLM_PROVIDER")  # "deepseek" or "openai"
    
    # Reply handling (GPT-4 for inbound replies)
    reply_confidence_threshold: float = Field(default=0.70, alias="REPLY_CONFIDENCE_THRESHOLD")
    auto_reply_enabled: bool = Field(default=True, alias="AUTO_REPLY_ENABLED")
    human_notification_email: str = Field(default="", alias="HUMAN_NOTIFICATION_EMAIL")
    # Delay before sending auto-reply (seconds); random between min and max minutes, converted to seconds when used
    reply_delay_min_minutes: int = Field(default=30, alias="REPLY_DELAY_MIN_MINUTES")
    reply_delay_max_minutes: int = Field(default=90, alias="REPLY_DELAY_MAX_MINUTES")
    
    # GPT-4 specific settings
    gpt4_model: str = Field(default="gpt-4-0125-preview", alias="GPT4_MODEL")
    gpt4_temperature: float = Field(default=0.3, alias="GPT4_TEMPERATURE")
    gpt4_max_tokens: int = Field(default=300, alias="GPT4_MAX_TOKENS")
    
    class Config:
        env_prefix = ""


class ApifyConfig(BaseSettings):
    """Apify lead sourcing configuration"""
    # Rotation strategy
    rotation_strategy: str = Field(default="round_robin")
    run_timeout_seconds: int = Field(default=300)
    max_runs_per_tick: int = Field(default=2, alias="APIFY_MAX_RUNS_PER_TICK")
    
    # Search parameters (comma-separated lists)
    industries: str = Field(
        default="law,accounting,medical,consulting,technology,financial_services,real_estate,insurance,engineering,architecture",
        alias="APIFY_INDUSTRIES"
    )
    states: str = Field(
        default="Texas,Florida,California,Georgia,New York,North Carolina,Arizona,Tennessee,Washington,Colorado",
        alias="APIFY_STATES"
    )
    employee_sizes: str = Field(
        default="11-20,21-50,51-100,101-200,201-500",
        alias="APIFY_EMPLOYEE_SIZES"
    )
    job_titles: str = Field(
        default="Owner,Managing Partner,Founder,CEO,President,Partner,Principal",
        alias="APIFY_JOB_TITLES"
    )
    
    @property
    def industries_list(self) -> List[str]:
        """Parse industries from comma-separated string"""
        return [i.strip() for i in self.industries.split(",") if i.strip()]
    
    @property
    def states_list(self) -> List[str]:
        """Parse states from comma-separated string"""
        return [s.strip() for s in self.states.split(",") if s.strip()]
    
    @property
    def sizes_list(self) -> List[str]:
        """Parse employee sizes from comma-separated string"""
        return [s.strip() for s in self.employee_sizes.split(",") if s.strip()]
    
    @property
    def titles_list(self) -> List[str]:
        """Parse job titles from comma-separated string"""
        return [t.strip() for t in self.job_titles.split(",") if t.strip()]
    
    @property
    def tokens(self) -> List[str]:
        """
        Dynamically load all APIFY_API_TOKEN_* vars (supports up to 24).
        
        Checks for:
        - APIFY_API_TOKEN (base)
        - APIFY_API_TOKEN_2 through APIFY_API_TOKEN_24
        """
        tokens = []
        
        # Check base token
        base_token = os.getenv("APIFY_API_TOKEN")
        if base_token:
            tokens.append(base_token)
        
        # Check numbered tokens (2-24)
        for i in range(2, 25):
            token = os.getenv(f"APIFY_API_TOKEN_{i}")
            if token:
                tokens.append(token)
        
        return tokens
    
    @property
    def actors(self) -> List[str]:
        """
        Dynamically load all APIFY_ACTOR_* vars (supports up to 24).
        
        Checks for:
        - APIFY_ACTOR_1 through APIFY_ACTOR_24
        """
        actors = []
        
        for i in range(1, 25):
            actor = os.getenv(f"APIFY_ACTOR_{i}")
            if actor:
                actors.append(actor)
        
        return actors
    
    class Config:
        env_prefix = ""


class MessagingConfig(BaseSettings):
    """Messaging and template configuration"""
    template_variants_per_stage: int = Field(default=5)
    randomize_templates: bool = Field(default=True)
    max_follow_ups: int = Field(default=3, alias="MAX_FOLLOW_UPS")
    
    class Config:
        env_prefix = ""


class ScoringConfig(BaseSettings):
    """Lead scoring configuration - adjustable weights and thresholds"""
    
    # Component weights (how much each factor contributes to total score)
    industry_weight: float = Field(default=0.35, alias="SCORING_INDUSTRY_WEIGHT")
    employee_size_weight: float = Field(default=0.25, alias="SCORING_EMPLOYEE_WEIGHT")
    business_age_weight: float = Field(default=0.20, alias="SCORING_AGE_WEIGHT")
    location_weight: float = Field(default=0.15, alias="SCORING_LOCATION_WEIGHT")
    contact_quality_weight: float = Field(default=0.05, alias="SCORING_CONTACT_WEIGHT")
    
    # Tier cutoffs (scores >= threshold get that tier)
    tier_1_min_score: int = Field(default=80, alias="SCORING_TIER_1_MIN")  # Premium leads
    tier_2_min_score: int = Field(default=65, alias="SCORING_TIER_2_MIN")  # High quality
    tier_3_min_score: int = Field(default=50, alias="SCORING_TIER_3_MIN")  # Good
    tier_4_min_score: int = Field(default=35, alias="SCORING_TIER_4_MIN")  # Acceptable
    # tier_5 = anything below tier_4_min_score
    
    # Optimal ranges (for max points in each category)
    optimal_employee_min: int = Field(default=20, alias="SCORING_OPTIMAL_EMP_MIN")
    optimal_employee_max: int = Field(default=50, alias="SCORING_OPTIMAL_EMP_MAX")
    optimal_age_min: int = Field(default=3, alias="SCORING_OPTIMAL_AGE_MIN")
    optimal_age_max: int = Field(default=7, alias="SCORING_OPTIMAL_AGE_MAX")
    
    class Config:
        env_prefix = ""


class WorkflowConfig(BaseSettings):
    """Workflow and scheduling configuration"""
    apify_run_interval_hours: int = Field(default=6, alias="APIFY_RUN_INTERVAL_HOURS")
    follow_up_delay_hours: int = Field(default=24, alias="FOLLOW_UP_DELAY_HOURS")
    auto_start_conversations: bool = Field(default=True, alias="AUTO_START_CONVERSATIONS")
    email_verification_enabled: bool = Field(default=True, alias="EMAIL_VERIFICATION_ENABLED")
    # NOTE: tier_threshold removed - ALL leads with emails now get contacted
    reminder_24h_enabled: bool = Field(default=True, alias="REMINDER_24H_ENABLED")
    reminder_2h_enabled: bool = Field(default=True, alias="REMINDER_2H_ENABLED")
    
    # Warmup mode
    warmup_mode: bool = Field(default=True, alias="WARMUP_MODE")
    warmup_start_date: str = Field(default="2026-01-20", alias="WARMUP_START_DATE")  # YYYY-MM-DD
    
    class Config:
        env_prefix = ""


class ComplianceConfig(BaseSettings):
    """Compliance configuration"""
    physical_address: str = Field(default="123 Main St, City, State 12345", alias="PHYSICAL_ADDRESS")
    unsubscribe_url: str = Field(default="https://example.com/unsubscribe", alias="UNSUBSCRIBE_URL")
    
    class Config:
        env_prefix = ""


class AppConfig(BaseSettings):
    """Application-level configuration"""
    name: str = Field(default="IUL Appointment Setter", alias="APP_NAME")
    env: str = Field(default="development", alias="APP_ENV")  # development, production
    debug: bool = Field(default=True, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    secret_key: str = Field(default="change-me-in-production", alias="SECRET_KEY")
    api_key: str = Field(default="", alias="API_KEY")
    
    class Config:
        env_prefix = ""


class Settings:
    """Global settings instance - loads all config at once"""
    
    def __init__(self):
        # Load from .env in ITORO root (like imela does)
        self._load_itoro_env()
        
        # Initialize all config sections
        self.database = DatabaseConfig()
        self.redis = RedisConfig()
        self.sendgrid = SendGridConfig()
        self.twilio = TwilioConfig()
        self.calendly = CalendlyConfig()
        self.llm = LLMConfig()
        self.apify = ApifyConfig()
        self.messaging = MessagingConfig()
        self.scoring = ScoringConfig()
        self.workflow = WorkflowConfig()
        self.compliance = ComplianceConfig()
        self.app = AppConfig()
    
    def _load_itoro_env(self):
        """Load .env from ITORO root (like imela does)"""
        try:
            # Find ITORO root
            current = Path(__file__).parent  # src directory
            project_root = current.parent  # iul-appointment-setter
            igwe_src = project_root.parent.parent  # igwe/src
            igwe = igwe_src.parent  # igwe
            agent_systems = igwe.parent  # agent-systems
            itoro_root = agent_systems.parent  # ITORO
            env_file = itoro_root / '.env'
            
            if env_file.exists():
                from dotenv import load_dotenv
                load_dotenv(env_file)
        except Exception:
            # Fallback to local .env
            from dotenv import load_dotenv
            load_dotenv()


# Global settings instance
settings = Settings()


# Convenience exports
db_config = settings.database
redis_config = settings.redis
sendgrid_config = settings.sendgrid
twilio_config = settings.twilio
calendly_config = settings.calendly
llm_config = settings.llm
apify_config = settings.apify
messaging_config = settings.messaging
scoring_config = settings.scoring
workflow_config = settings.workflow
compliance_config = settings.compliance
app_config = settings.app
