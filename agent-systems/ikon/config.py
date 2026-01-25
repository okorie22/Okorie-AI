"""
Configuration file for ZerePy Content Pipeline
Centralized configuration for all pipeline agents
"""

import os
from pathlib import Path

# Load environment variables
# Note: Environment variables are loaded by main.py from the ITORO root .env file
# This ensures proper handling of null characters and encoding issues

# ==========================================
# GENERAL SETTINGS
# ==========================================

# Project paths
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
CONTENT_PIPELINE_DIR = DATA_DIR / "content_pipeline"
COMPLIANCE_DIR = DATA_DIR / "compliance"

# Create directories if they don't exist
CONTENT_PIPELINE_DIR.mkdir(parents=True, exist_ok=True)
COMPLIANCE_DIR.mkdir(parents=True, exist_ok=True)

# ==========================================
# GALLERY AGENT CONFIGURATION
# ==========================================

GALLERY_CONFIG = {
    # Cloud folder to monitor for new videos
    "cloud_folder_path": r"C:\Users\Top Cash Pawn\iCloudDrive\Videos",

    # File patterns to monitor
    "file_patterns": [".mp4", ".mov", ".avi", ".mkv"],

    # Check interval in seconds
    "check_interval": 60,

    # Processing folder for raw videos
    "processing_folder": str(CONTENT_PIPELINE_DIR / "raw_videos"),

    # Maximum file age to process (days) - for cleanup
    "max_file_age_days": 30
}

# ==========================================
# CLIPS AGENT CONFIGURATION
# ==========================================

CLIPS_CONFIG = {
    # Target clip duration range (seconds)
    "target_duration_min": 15,
    "target_duration_max": 60,

    # Number of clip candidates to generate per video
    "num_clips": 3,

    # Whisper model for transcription
    "whisper_model": "base",  # Options: tiny, base, small, medium, large

    # AI model for clip analysis
    "ai_model": "deepseek-chat",

    # Audio analysis settings
    "volume_threshold": 0.1,  # Minimum volume change to detect
    "silence_threshold": 1.0,  # Seconds of silence to detect pauses

    # Processing folders
    "processed_clips_dir": str(CONTENT_PIPELINE_DIR / "processed_clips"),
    "temp_dir": str(CONTENT_PIPELINE_DIR / "temp")
}

# ==========================================
# EDITING AGENT CONFIGURATION
# ==========================================

EDITING_CONFIG = {
    # Output format settings
    "output_format": "shorts",  # 'shorts' (9:16) or 'square' (1:1)
    "target_resolution": "1080p",  # '1080p' or '4k'

    # Editing options
    "add_captions": True,  # Add text overlays from transcript
    "background_music": False,  # Add background music
    "auto_color_correction": True,  # Apply auto color correction
    "denoise": True,  # Apply video denoising
    "sharpen": True,  # Apply sharpening
    "stabilize": False,  # Apply video stabilization (expensive)

    # Font settings for captions
    "caption_font": "/Windows/Fonts/arial.ttf",  # Windows font path
    "caption_fontsize": 32,
    "caption_color": "white",
    "caption_box_color": "black@0.5",

    # Output folders
    "edited_clips_dir": str(CONTENT_PIPELINE_DIR / "edited_clips"),
    "music_library_dir": str(CONTENT_PIPELINE_DIR / "music_library")
}

# ==========================================
# REVIEW AGENT CONFIGURATION
# ==========================================

REVIEW_CONFIG = {
    # Email settings
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "email_address": "chibuokem.okorie@gmail.com",  # Your Gmail (sender)
    "email_password": os.getenv("GMAIL_APP_PASSWORD", ""),  # From environment variable
    "review_email": "contact@okemokorie.com",   # Your Zoho email (receiver)

    # Review settings
    "timeout_hours": 24,  # Auto-reject after this many hours
    "max_clips_per_email": 5,  # Maximum clips to send per email
    "email_subject_template": "🎬 New clips ready for review - {filename}",

    # IMAP settings (optional - for reading responses)
    "imap_host": "imap.gmail.com",
    "imap_port": 993,

    # Response parsing
    "approve_keywords": ["approve", "yes", "good", "accept"],
    "reject_keywords": ["reject", "no", "bad", "deny"],

    # Output folders
    "review_pending_dir": str(CONTENT_PIPELINE_DIR / "review_pending")
}

# ==========================================
# PUBLISHING AGENT CONFIGURATION
# ==========================================

PUBLISHING_CONFIG = {
    # Publishing settings
    "auto_publish": True,  # Auto-publish to YouTube or just prepare
    "publish_to_youtube": True,
    "prepare_for_instagram": True,

    # YouTube settings
    "youtube_title_template": "{clip_title} - {date}",
    "youtube_description_template": "{description}\n\n#Shorts #{hashtags}",
    "youtube_category_id": "22",  # People & Blogs
    "youtube_privacy_status": "public",  # public, private, unlisted

    # Instagram settings
    "instagram_folder": str(CONTENT_PIPELINE_DIR / "instagram_ready"),

    # Metadata generation
    "generate_titles": True,
    "generate_descriptions": True,
    "default_hashtags": ["shorts", "content", "video", "clips"],

    # Output folders
    "published_dir": str(CONTENT_PIPELINE_DIR / "published"),
    "rejected_dir": str(CONTENT_PIPELINE_DIR / "rejected")
}

# ==========================================
# COMPLIANCE AGENT CONFIGURATION
# ==========================================

COMPLIANCE_CONFIG = {
    # Platform to check compliance for
    "platform": "youtube",  # 'youtube' or 'instagram'

    # Guidelines file paths
    "youtube_guidelines_path": str(COMPLIANCE_DIR / "youtube_guidelines.txt"),
    "instagram_guidelines_path": str(COMPLIANCE_DIR / "instagram_guidelines.txt"),

    # Compliance thresholds
    "enabled": True,
    "min_score_threshold": 0.5,  # 0.0-1.0, videos below this are rejected
    "quick_check": True,  # Fast check mode for pipeline

    # AI model for compliance analysis
    "ai_model": "deepseek-chat",

    # Frame extraction settings
    "frames_to_extract": 5 if True else 10,  # Fewer frames for quick check
    "transcript_length_limit": 2000,  # Characters to analyze

    # Output folders
    "reports_dir": str(COMPLIANCE_DIR / "reports"),
    "frames_dir": str(COMPLIANCE_DIR / "frames"),
    "transcripts_dir": str(COMPLIANCE_DIR / "transcripts")
}

# ==========================================
# PIPELINE MANAGER CONFIGURATION
# ==========================================

PIPELINE_CONFIG = {
    # Database settings
    "db_path": str(DATA_DIR / "pipeline.db"),

    # Pipeline states
    "state_timeout_hours": {
        "new_video": 1,
        "compliance_check": 0.5,
        "processing": 2,
        "clipping": 5,
        "editing": 10,
        "review_pending": 24,
        "approved": 1,
        "published": 168  # 1 week
    },

    # Cleanup settings
    "cleanup_old_pipelines_days": 30,
    "max_active_pipelines": 10,

    # Logging
    "log_level": "INFO",
    "log_file": str(DATA_DIR / "pipeline.log")
}

# ==========================================
# AI/LLM CONFIGURATION
# ==========================================

AI_CONFIG = {
    # DeepSeek settings (primary AI model)
    "deepseek_key": os.getenv("DEEPSEEK_KEY", ""),
    "deepseek_model": "deepseek-chat",
    "deepseek_base_url": "https://api.deepseek.com",

    # Fallback models
    "fallback_models": [
        "openai/gpt-4o-mini",
        "anthropic/claude-3-haiku"
    ],

    # API settings
    "temperature": 0.7,
    "max_tokens": 2000,
    "reasoning_effort": "medium",

    # Rate limiting
    "requests_per_minute": 30,
    "burst_limit": 10
}

# ==========================================
# PIPELINE MODES CONFIGURATION
# ==========================================

PIPELINE_MODES = {
    "talking_head": {
        "enabled": True,
        "input_type": "single_video",
        "description": "Extract best clips from short-form talking head videos",
        "processing_steps": ["compliance", "clipping", "editing", "review", "publishing"],
        "target_duration": {"min": 15, "max": 60},
        "processor_class": "ClipExtractor",
        "editing_profile": {
            "format": "shorts",
            "captions": True,
            "color_correction": True,
            "denoise": True,
            "sharpen": True
        }
    },
    "condensation": {
        "enabled": True,
        "input_type": "single_video",
        "description": "Condense long-form videos into engaging shorts while preserving narrative flow",
        "processing_steps": ["compliance", "condensation", "editing", "review", "publishing"],
        "min_source_duration": 300,  # 5 minutes minimum
        "preserve_narrative_flow": True,
        "processor_class": "VideoCondenser",
        "editing_profile": {
            "format": "shorts",
            "captions": True,
            "smooth_transitions": True,
            "fade_duration": 0.5,  # seconds
            "audio_ducking": True,
            "flow_preservation": True
        }
    },
    "compilation": {
        "enabled": True,
        "input_type": "multi_video",
        "description": "Combine multiple videos into one cohesive short video",
        "processing_steps": ["compliance", "compilation", "editing", "review", "publishing"],
        "min_source_videos": 2,
        "max_source_videos": 5,
        "processor_class": "VideoCompiler",
        "editing_profile": {
            "format": "shorts",
            "captions": True,
            "cross_fade_duration": 1.0,  # seconds
            "transition_style": "smooth",  # smooth, dissolve, wipe
            "audio_mixing": True,
            "audio_normalization": True,
            "consistent_color_grading": True
        }
    },
    "ai_generation": {
        "enabled": False,  # Placeholder - requires API setup
        "input_type": "text_prompt",
        "description": "Generate video content from text prompts using AI (requires API keys)",
        "processing_steps": ["generate", "enhance", "compliance", "publishing"],
        "processor_class": "AIGenerator",
        "api_providers": {
            "runwayml": {"enabled": False, "api_key": os.getenv("RUNWAYML_API_KEY", "")},
            "pika": {"enabled": False, "api_key": os.getenv("PIKA_API_KEY", "")},
            "stable_diffusion": {"enabled": False, "api_key": os.getenv("STABLE_DIFFUSION_API_KEY", "")}
        },
        "editing_profile": {
            "format": "shorts",
            "upscale": True,
            "enhance_quality": True,
            "apply_effects": False
        }
    }
}

# Folder-based mode detection mapping
FOLDER_MODE_MAPPING = {
    "videos_talking_head": "talking_head",
    "talking_head": "talking_head",
    "videos_condensation": "condensation",
    "condensation": "condensation",
    "condense": "condensation",
    "videos_compilation": "compilation",
    "compilation": "compilation",
    "compile": "compilation",
    "prompts_ai_generation": "ai_generation",
    "ai_generation": "ai_generation",
    "prompts": "ai_generation",
    "videos_auto": "auto_detect",
    "auto": "auto_detect"
}

# Filename pattern detection (regex patterns)
FILENAME_PATTERNS = {
    r"^talking_head_": "talking_head",
    r"^th_": "talking_head",
    r"^condense_": "condensation",
    r"^condensation_": "condensation",
    r"^long_": "condensation",
    r"^compile_": "compilation",
    r"^compilation_": "compilation",
    r"^part\d+": "compilation",  # part1, part2, etc.
    r"^ai_.*\.txt$": "ai_generation",
    r"^prompt_.*\.txt$": "ai_generation",
    r"^generate_.*\.txt$": "ai_generation"
}

# Compilation mode specific configuration
COMPILATION_CONFIG = {
    # Timeout settings
    "timeout_minutes": 5,  # Wait 5 minutes after last video before compiling
    "check_interval_seconds": 30,  # How often to check for timeouts
    
    # Video limits
    "min_videos": 2,
    "max_videos": 5,
    
    # Processing settings
    "auto_sort_by_timestamp": True,  # Sort videos by creation time
    "allow_mixed_resolutions": True,  # Allow different video resolutions
    "target_total_duration": 60,  # Target total duration in seconds
    
    # Group detection
    "group_by_folder": True,  # Videos in same folder = same compilation
    "group_by_prefix": True,  # Videos with same prefix = same compilation
}

# Mode detection settings
MODE_DETECTION_CONFIG = {
    "enable_folder_detection": True,
    "enable_filename_detection": True,
    "enable_content_detection": True,
    "fallback_mode": "talking_head",
    
    # Content-based detection thresholds
    "long_video_threshold": 600,  # 10+ minutes = condensation candidate
    "short_video_threshold": 60,  # < 1 minute = talking_head
    "multi_video_check": True  # Check for multiple videos in folder
}

# ==========================================
# UTILITY FUNCTIONS
# ==========================================

def get_config_for_agent(agent_name: str) -> dict:
    """Get configuration for a specific agent"""
    config_map = {
        "gallery": GALLERY_CONFIG,
        "clips": CLIPS_CONFIG,
        "editing": EDITING_CONFIG,
        "review": REVIEW_CONFIG,
        "publishing": PUBLISHING_CONFIG,
        "compliance": COMPLIANCE_CONFIG,
        "pipeline": PIPELINE_CONFIG,
        "ai": AI_CONFIG,
        "modes": PIPELINE_MODES,
        "compilation": COMPILATION_CONFIG,
        "mode_detection": MODE_DETECTION_CONFIG
    }

    if agent_name not in config_map:
        raise ValueError(f"No configuration found for agent: {agent_name}")

    return config_map[agent_name]

def get_mode_config(mode: str) -> dict:
    """Get configuration for a specific pipeline mode"""
    if mode not in PIPELINE_MODES:
        raise ValueError(f"Unknown pipeline mode: {mode}. Available modes: {list(PIPELINE_MODES.keys())}")
    
    return PIPELINE_MODES[mode]

def get_enabled_modes() -> list:
    """Get list of enabled pipeline modes"""
    return [mode for mode, config in PIPELINE_MODES.items() if config.get("enabled", False)]

# ==========================================
# IUL PIPELINE CONFIGURATION
# ==========================================

IUL_PIPELINE_CONFIG = {
    # Compliance rules
    "blocked_phrases": [
        "guaranteed", 
        "risk-free", 
        "no risk", 
        "tax-free retirement guaranteed",
        "beats the market",
        "you should buy",
        "perfect for you",
        "your situation requires"
    ],
    "required_disclaimer": "Educational only. Not financial or insurance advice. Consult a licensed professional for personalized guidance.",
    "min_compliance_score": 0.80,
    "single_cta_policy": True,
    
    # Lead generation
    "cta_url_template": "https://yourdomain.com/free-guide?utm_source=youtube&utm_medium=shorts&utm_content={idea_id}",
    "cta_text_options": [
        "Download our free IUL checklist",
        "Get the free guide",
        "Learn more with our free checklist",
        "Grab your free IUL overview"
    ],
    
    # Script generation
    "target_script_length": 150,  # words for 30s at natural pace
    "script_word_range": [140, 160],
    "allow_2nd_draft": True,
    "2nd_draft_risk_threshold": [20, 40],
    
    # Pipeline settings
    "redis_url": os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    "queue_prefix": "ikon:",
    "max_job_attempts": 3,
    "job_backoff_seconds": [60, 300, 900],  # 1m, 5m, 15m
    
    # Output directories
    "ideas_dir": str(DATA_DIR / "ideas"),
    "audio_cache_dir": str(DATA_DIR / "audio_cache"),
    "rendered_videos_dir": str(DATA_DIR / "rendered_videos"),
    "thumbnails_dir": str(DATA_DIR / "thumbnails")
}

# ==========================================
# IUL INTELLIGENCE GATHERING CONFIGURATION
# ==========================================

IUL_INTEL_CONFIG = {
    # Competitor monitoring
    "competitors": [
        # Add your competitor channel IDs here
        # {"channel_id": "UCxxxxx", "label": "CompetitorA_IUL_Channel"},
        # {"channel_id": "UCyyyyy", "label": "CompetitorB_Insurance_Ed"},
    ],
    
    # Search keywords
    "search_keywords": [
        "IUL",
        "indexed universal life",
        "cash value life insurance",
        "infinite banking",
        "life insurance cash value",
        "IUL vs 401k",
        "permanent life insurance"
    ],
    
    # Gathering cadence (seconds)
    "gather_cadence": {
        "analytics": 1800,      # 30 minutes
        "competitors": 21600,   # 6 hours
        "search": 43200         # 12 hours
    },
    
    # Sampling settings (quota-aware)
    "analytics_sample_videos": 10,
    "competitor_sample_videos": 5,
    "search_trends_lookback_days": 30,
    
    # Data storage
    "intel_dir": str(DATA_DIR / "intel"),
    "analytics_history_file": str(DATA_DIR / "intel" / "analytics_history.jsonl"),
    "competitor_snapshots_file": str(DATA_DIR / "intel" / "competitor_snapshots.jsonl"),
    "search_trends_file": str(DATA_DIR / "intel" / "search_trends.json"),
    
    # Research agent settings
    "ideas_per_run": 5,
    "min_idea_score": 75,
    "max_compliance_risk": 20,
    "idea_cooldown_hours": 24  # Don't regenerate same topic within 24h
}

# Create IUL-specific directories
for key in ["ideas_dir", "audio_cache_dir", "rendered_videos_dir", "thumbnails_dir"]:
    Path(IUL_PIPELINE_CONFIG[key]).mkdir(parents=True, exist_ok=True)

Path(IUL_INTEL_CONFIG["intel_dir"]).mkdir(parents=True, exist_ok=True)

def validate_config() -> list:
    """Validate all configuration settings and return any issues"""
    issues = []

    # Check required directories exist
    required_dirs = [
        CONTENT_PIPELINE_DIR,
        COMPLIANCE_DIR,
        Path(GALLERY_CONFIG["processing_folder"]),
        Path(CLIPS_CONFIG["processed_clips_dir"]),
        Path(EDITING_CONFIG["edited_clips_dir"]),
        Path(PUBLISHING_CONFIG["instagram_folder"]),
        Path(PUBLISHING_CONFIG["published_dir"]),
        Path(COMPLIANCE_CONFIG["reports_dir"])
    ]

    for dir_path in required_dirs:
        if not dir_path.exists():
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                issues.append(f"Cannot create directory {dir_path}: {e}")

    # Check required files exist
    required_files = [
        Path(COMPLIANCE_CONFIG["youtube_guidelines_path"]),
        Path(COMPLIANCE_CONFIG["instagram_guidelines_path"])
    ]

    for file_path in required_files:
        if not file_path.exists():
            issues.append(f"Required file missing: {file_path}")

    # Check email configuration
    if not REVIEW_CONFIG["email_address"]:
        issues.append("Review email address not configured")

    if not REVIEW_CONFIG["email_password"]:
        issues.append("GMAIL_APP_PASSWORD environment variable not set")

    if not REVIEW_CONFIG["review_email"]:
        issues.append("Review recipient email not configured")

    # Check AI configuration
    if not AI_CONFIG["deepseek_key"]:
        issues.append("DEEPSEEK_KEY environment variable not set (required for AI features)")

    # Check cloud folder exists
    cloud_folder = Path(GALLERY_CONFIG["cloud_folder_path"])
    if not cloud_folder.exists():
        issues.append(f"Cloud folder does not exist: {cloud_folder}")

    return issues

# ==========================================
# IUL PIPELINE CONFIGURATION
# ==========================================

IUL_PIPELINE_CONFIG = {
    # Compliance rules
    "blocked_phrases": [
        "guaranteed",
        "risk-free",
        "no risk",
        "tax-free retirement guaranteed",
        "beats the market",
        "guaranteed returns",
        "zero risk",
        "can't lose",
        "you should buy",
        "you need this"
    ],
    
    # Required disclaimer
    "required_disclaimer": "Educational only. Not financial or insurance advice. Consult a licensed professional for personalized guidance.",
    
    # CTA configuration for lead generation
    "cta_url_template": "https://yourdomain.com/free-guide?utm_source=youtube&utm_medium=shorts&utm_content={idea_id}",
    "single_cta_policy": True,  # Only one CTA per video
    "cta_text_templates": [
        "Get the free checklist → link in description",
        "Download the free guide → see description",
        "Free resource available → check description"
    ],
    
    # Compliance thresholds
    "min_compliance_score": 0.80,  # 0-1 scale
    "auto_revision_threshold": 0.65,  # Attempt revision if between this and min
    
    # Script parameters
    "target_word_count": 150,  # For 30s video at natural pace
    "max_word_count": 175,
    "min_word_count": 130
}

# ==========================================
# IUL INTELLIGENCE GATHERING CONFIGURATION
# ==========================================

IUL_INTEL_CONFIG = {
    # Competitor channels to monitor (seed list - edit with your actual competitors)
    "competitors": [
        {"channel_id": "UCxxxxx", "label": "CompetitorA_IUL_Channel", "priority": "high"},
        {"channel_id": "UCyyyyy", "label": "CompetitorB_Insurance_Ed", "priority": "medium"},
        {"channel_id": "UCzzzzz", "label": "CompetitorC_FinancialEd", "priority": "medium"}
    ],
    
    # Search keywords for trends monitoring
    "search_keywords": [
        "IUL",
        "indexed universal life",
        "cash value life insurance",
        "infinite banking",
        "IUL explained",
        "life insurance cash value",
        "IUL vs 401k",
        "IUL pros and cons"
    ],
    
    # Gathering cadence (seconds)
    "gather_cadence": {
        "analytics": 1800,      # 30 minutes
        "competitors": 21600,   # 6 hours
        "search": 43200         # 12 hours
    },
    
    # Quota management
    "quota_limits": {
        "youtube_daily": 8000,  # Leave buffer from 10K daily limit
        "competitor_videos_per_check": 5,  # Recent videos to analyze
        "own_videos_sample": 10  # Recent own videos to analyze
    },
    
    # Data retention
    "retention_days": {
        "analytics_snapshots": 90,
        "competitor_snapshots": 30,
        "search_trends": 30
    }
}

# ==========================================
# REDIS QUEUE CONFIGURATION
# ==========================================

REDIS_CONFIG = {
    "url": os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    "namespace": "ikon",
    
    # Queue names
    "queues": {
        "ideas_ready": "ideas:ready",
        "ideas_dead": "ideas:dead",
        "pipeline_tts": "pipeline:tts",
        "pipeline_render": "pipeline:render",
        "pipeline_publish": "pipeline:publish",
        "engagement_inbox": "engagement:inbox"
    },
    
    # Job retry configuration
    "max_attempts": 3,
    "backoff_delays": [60, 300, 900],  # 1m, 5m, 15m
    
    # Connection settings
    "socket_timeout": 5,
    "socket_connect_timeout": 5,
    "retry_on_timeout": True
}

def print_config_summary():
    """Print a summary of all configuration settings"""
    print("🔧 ZerePy Content Pipeline Configuration")
    print("=" * 50)

    print(f"📁 Project Root: {PROJECT_ROOT}")
    print(f"📁 Data Directory: {DATA_DIR}")
    print(f"📁 Pipeline Directory: {CONTENT_PIPELINE_DIR}")

    print(f"\n🏠 Gallery Agent:")
    print(f"  📂 Cloud Folder: {GALLERY_CONFIG['cloud_folder_path']}")
    print(f"  📋 File Patterns: {GALLERY_CONFIG['file_patterns']}")

    print(f"\n✂️  Clips Agent:")
    print(f"  ⏱️  Duration: {CLIPS_CONFIG['target_duration_min']}-{CLIPS_CONFIG['target_duration_max']}s")
    print(f"  🎯 Clips per video: {CLIPS_CONFIG['num_clips']}")

    print(f"\n🎬 Editing Agent:")
    print(f"  📐 Format: {EDITING_CONFIG['output_format']} ({EDITING_CONFIG['target_resolution']})")
    print(f"  📝 Captions: {EDITING_CONFIG['add_captions']}")

    print(f"\n📧 Review Agent:")
    print(f"  📧 SMTP: {REVIEW_CONFIG['smtp_host']}:{REVIEW_CONFIG['smtp_port']}")
    email_configured = bool(REVIEW_CONFIG['email_password'])
    print(f"  📧 Email configured: {'✅' if email_configured else '❌'}")
    print(f"  ⏰ Timeout: {REVIEW_CONFIG['timeout_hours']} hours")

    print(f"\n📤 Publishing Agent:")
    print(f"  🚀 Auto-publish: {PUBLISHING_CONFIG['auto_publish']}")
    print(f"  📱 Instagram prep: {PUBLISHING_CONFIG['prepare_for_instagram']}")

    print(f"\n🔍 Compliance Agent:")
    print(f"  🎯 Platform: {COMPLIANCE_CONFIG['platform']}")
    print(f"  ✅ Enabled: {COMPLIANCE_CONFIG['enabled']}")
    print(f"  📊 Threshold: {COMPLIANCE_CONFIG['min_score_threshold']}")

    print(f"\n🎭 Pipeline Modes:")
    enabled_modes = get_enabled_modes()
    print(f"  ✅ Enabled Modes: {', '.join(enabled_modes)}")
    for mode, config in PIPELINE_MODES.items():
        status = "✅" if config.get("enabled") else "⏸️ "
        print(f"  {status} {mode}: {config.get('description', 'N/A')}")

    print(f"\n📁 Mode Detection:")
    print(f"  📂 Folder detection: {MODE_DETECTION_CONFIG['enable_folder_detection']}")
    print(f"  📝 Filename detection: {MODE_DETECTION_CONFIG['enable_filename_detection']}")
    print(f"  🔍 Content detection: {MODE_DETECTION_CONFIG['enable_content_detection']}")
    print(f"  🎯 Fallback mode: {MODE_DETECTION_CONFIG['fallback_mode']}")

    issues = validate_config()
    if issues:
        print(f"\n⚠️  Configuration Issues ({len(issues)}):")
        for issue in issues:
            print(f"  ❌ {issue}")
    else:
        print(f"\n✅ Configuration validation passed!")

if __name__ == "__main__":
    print_config_summary()
