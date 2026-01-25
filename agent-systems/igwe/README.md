# IUL Appointment Setter System

An autonomous appointment setter that transforms scored leads into booked appointments through intelligent conversation, multi-channel outreach (email-first, SMS opt-in), and automated scheduling.

**✨ NEW: Automated Apify lead sourcing + Human-like template variants + ChatGPT-quality inbound reply handling**

## Architecture

This system reuses proven components from the Lead_Pipeline system and adds:
- **Automated Lead Sourcing** via Apify (Apollo scraping with rotation)
- **Stateful workflow orchestration** (Celery-based)
- **LLM-powered conversations** with guardrails
- **Human-like template variants** (5+ per stage, randomized)
- **ChatGPT-quality inbound reply handling** (GPT-4 with hybrid AI-human escalation)
- **Multi-channel outreach** (Email, SMS, Manual)
- **Automated scheduling and reminders**
- **Revenue attribution tracking**

## Project Structure

```
iul-appointment-setter/
├── main.py              # 🆕 Single entry point launcher
├── src/
│   ├── config.py        # 🆕 Centralized configuration
│   ├── sources/         # 🆕 Apify integration + param rotation
│   ├── ingestion/       # Lead normalization and import
│   ├── intelligence/    # Scoring and enrichment workers
│   ├── workflow/        # State machine and scheduler
│   ├── conversation/    # 🆕 Template variants + LLM agent
│   ├── channels/        # Email/SMS/manual adapters
│   ├── scheduling/      # Calendly integration
│   ├── storage/         # Database models and repositories
│   └── api/             # 🆕 FastAPI webhooks + Apify endpoints
├── config/              # Configuration files
├── scripts/
│   ├── quick_start.bat  # 🆕 Windows launcher
│   ├── quick_start.sh   # 🆕 Linux/Mac launcher
│   ├── test_apify.py    # 🆕 Apify integration tests
│   └── test_templates.py # 🆕 Template variant tests
└── requirements.txt     # Python dependencies
```

## Quick Start (Easiest)

**Option 1: Single Command**

```bash
# Windows
scripts\quick_start.bat

# Linux/Mac
chmod +x scripts/quick_start.sh
./scripts/quick_start.sh
```

This starts Redis + all system services automatically.

**Option 2: Python Main Launcher**

```bash
python main.py
```

This will:
- ✅ Check Redis connection
- ✅ Initialize database
- ✅ Validate environment configuration
- ✅ Start Celery worker
- ✅ Start Celery beat scheduler
- ✅ Start FastAPI server

## Manual Setup (Advanced)

### 1. Install Dependencies

```bash
cd C:\Users\Top Cash Pawn\ITORO\agent-systems\igwe\src\iul-appointment-setter
pip install -r requirements.txt
```

### 2. Configure Environment

The system uses the ITORO root `.env` file (like `imela`). Add these configuration variables:

```bash
# Apify Configuration (supports up to 24 tokens)
APIFY_API_TOKEN=apify_api_xxx1
APIFY_API_TOKEN_2=apify_api_xxx2
APIFY_API_TOKEN_3=apify_api_xxx3
# Add more as needed: APIFY_API_TOKEN_4 through APIFY_API_TOKEN_24

APIFY_ACTOR_1=code_crafter~leads-finder
APIFY_ACTOR_2=pipelinelabs~lead-scraper-apollo-zoominfo-lusha-ppe
# Add more as needed: APIFY_ACTOR_3 through APIFY_ACTOR_24

# Apify Search Parameters (customize targeting)
APIFY_MAX_RUNS_PER_TICK=2  # Runs per 2-hour tick
APIFY_INDUSTRIES=law,accounting,medical,consulting,technology,financial_services,real_estate,insurance,engineering,architecture
APIFY_STATES=Texas, United States,Florida, United States,California, United States,Georgia, United States,New York, United States,North Carolina, United States,Arizona, United States,Tennessee, United States,Washington, United States,Colorado, United States
APIFY_EMPLOYEE_SIZES=10-19,20-50,51-100,101-250,251-500
APIFY_JOB_TITLES=Owner,Managing Partner,Founder,CEO,President,Partner,Principal

# SendGrid
SENDGRID_API_KEY=your_key
SENDGRID_FROM_EMAIL=you@example.com
SENDGRID_FROM_NAME=Your Name
SENDGRID_TEST_MODE=False  # Set to True to prevent actual emails (testing only)

# Twilio (optional - for SMS)
TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_token
TWILIO_PHONE_NUMBER=+15551234567
TWILIO_TEST_MODE=False  # Set to True to prevent actual SMS (testing only)

# Calendly
CALENDLY_API_KEY=your_key
CALENDLY_EVENT_TYPE_UUID=your_event_uuid
CALENDLY_USER_URI=https://calendly.com/your-link

# LLM Provider
DEEPSEEK_API_KEY=your_key
# or
OPENAI_API_KEY=your_key
LLM_PROVIDER=deepseek

# GPT-4 for Inbound Reply Handling (REQUIRED for auto-replies)
OPENAI_API_KEY=sk-your-openai-api-key-here
HUMAN_NOTIFICATION_EMAIL=your-email@example.com
REPLY_CONFIDENCE_THRESHOLD=0.75  # Minimum confidence for auto-reply (0.0-1.0)
AUTO_REPLY_ENABLED=True
GPT4_MODEL=gpt-4-0125-preview
GPT4_TEMPERATURE=0.3
GPT4_MAX_TOKENS=300

# Workflow
AUTO_START_CONVERSATIONS=True
TIER_THRESHOLD_FOR_AUTO_START=2
TEMPLATE_RANDOMIZATION=True

# SendGrid Warmup & Throttling
SENDGRID_WARMUP_MODE=True
SENDGRID_DAILY_CAP=50  # Auto-managed by warmup
SENDGRID_HOURLY_CAP=10
SENDGRID_BATCH_SIZE=20
SENDGRID_SEND_START_HOUR=8  # 8 AM EST
SENDGRID_SEND_END_HOUR=17   # 5 PM EST
SENDGRID_WEEKDAYS_ONLY=True
SENDGRID_TEST_MODE=False  # Set to True for testing without actual sends

# Warmup Mode
WARMUP_MODE=True
WARMUP_START_DATE=2026-01-20  # Set to your go-live date

# Compliance
PHYSICAL_ADDRESS=123 Main St, City, State 12345
UNSUBSCRIBE_URL=https://example.com/unsubscribe
```

### 3. Setup Database

```bash
# For development (SQLite)
python scripts/setup_db.py

# For production (PostgreSQL)
# First ensure PostgreSQL is running, then:
alembic upgrade head
```

### 4. Start Redis (for Celery)

```bash
# Install and start Redis
# Windows: Download from https://github.com/microsoftarchive/redis/releases
redis-server
```

### 5. Start Workers

```bash
# Terminal 1: Start Celery worker
celery -A src.workflow.celery_app worker --loglevel=info

# Terminal 2: Start Celery beat (scheduler)
celery -A src.workflow.celery_app beat --loglevel=info

# Terminal 3: Start FastAPI server
uvicorn src.api.main:app --reload --port 8000
```

## Usage

### Automated Lead Sourcing (Apify)

The system automatically imports leads from Apify every 2 hours (during warmup) or 6 hours (post-warmup). Each tick runs up to `APIFY_MAX_RUNS_PER_TICK` actor runs (default: 2) until daily quota is met.

**Customize Targeting:**
```bash
# In .env file
APIFY_INDUSTRIES=law,medical,financial_services
APIFY_STATES=California, United States,Texas, United States
APIFY_EMPLOYEE_SIZES=51-100,101-250
APIFY_JOB_TITLES=Owner,CEO,President
APIFY_MAX_RUNS_PER_TICK=3  # Increase for more leads per tick
```

To trigger manually:

```bash
# Via API
curl -X POST http://localhost:8000/api/sources/apify/run

# Via Python
python -c "from src.workflow.tasks import run_apify_import; run_apify_import.delay()"
```

View Apify run history:

```
http://localhost:8000/api/sources/apify/runs
```

### Manual Lead Import (CSV)

```bash
python scripts/import_csv.py data/leads.csv
```

### Test Conversation Flow

```bash
python scripts/test_conversation.py --lead-id 1
```

### View Dashboard

```
http://localhost:8000/dashboard
```

### API Endpoints

**Webhooks:**
- `POST /webhooks/sendgrid` - Handle email delivery events (bounces, opens, clicks)
- `POST /webhooks/sendgrid/inbound` - Handle inbound email replies (with AI reply agent)
- `POST /webhooks/twilio` - Handle SMS replies (with AI reply agent)
- `POST /webhooks/calendly` - Handle appointment events

**Lead Management:**
- `GET /api/leads` - List leads
- `GET /api/conversations` - List conversations
- `GET /api/appointments` - List appointments
- `GET /api/metrics` - Get analytics metrics

**🆕 Apify Source Management:**
- `POST /api/sources/apify/run` - Trigger Apify import manually (with optional parameters)
- `GET /api/sources/apify/runs` - List recent Apify runs with detailed stats
- `GET /api/sources/apify/stats` - Get aggregate Apify statistics (total runs, leads imported, duplicates)

**Example: Manual Apify Import**
```bash
# Trigger with custom parameters
curl -X POST "http://localhost:8000/api/sources/apify/run?industry=law&state=Texas, United States"

# View recent runs
curl http://localhost:8000/api/sources/apify/runs?limit=10
```

## Key Features

### 🆕 Automated Lead Sourcing
- **Apify Integration**: Scrapes Apollo and other directories automatically
- **Multi-Run Per Tick**: Runs up to `APIFY_MAX_RUNS_PER_TICK` actor runs per 2-hour interval (default: 2)
- **Token Rotation**: Distributes load across up to 24 Apify accounts
- **Configurable Parameters**: Industries, states, employee sizes, and job titles configurable via `.env`
- **Parameter Rotation**: Systematically varies search parameters for diversity (tracks used combinations)
- **Smart Quota Management**: Automatically stops when daily lead quota is met
- **Deduplication**: Hard deduplication by email/phone (unique database constraints)
- **Field Mapping**: Normalizes Apify CSV data to database schema

### 🆕 Human-Like Messaging
- **Template Variants**: 5-6 variations per stage (opener, follow-ups, SMS, reminders)
- **Randomization**: Never sends the same variant twice to the same lead
- **Low-Hype Tone**: Casual, short, single-question format
- **Compliance Built-In**: TCPA/CAN-SPAM compliant out of the box
- **A/B Testing Ready**: Tracks which variants get better responses

### 🆕 ChatGPT-Quality Inbound Reply Handling
- **GPT-4 Powered**: Uses GPT-4 for intelligent reply analysis and generation
- **Hybrid AI-Human**: Auto-replies to simple queries (60-70%), escalates complex/compliance-sensitive (30-40%)
- **Confidence Gating**: Only auto-replies when confidence ≥ threshold (default: 0.75)
- **Multi-Layer Safety**: Pre-screening, sentiment analysis, compliance checks, response validation
- **Intent Classification**: Automatically categorizes replies (interested, scheduling, questions, objections, complaints)
- **Email Escalation Alerts**: Beautiful HTML notifications when human review needed
- **Auto-Unsubscribe**: Handles unsubscribe requests automatically
- **Compliance Safeguards**: Never makes guarantees, avoids tax/legal advice, sanitizes responses

### Lead Processing
- Reuses Lead_Pipeline normalization, scoring, and enrichment
- Automatic deduplication
- Consent tracking (email/SMS)

### Conversation Management
- **Batched Processing**: Processes up to `SENDGRID_BATCH_SIZE` conversations per 10-minute tick
- **State Filtering**: Only processes `NEW`, `CONTACTED`, `NO_RESPONSE` states (skips others)
- **Deterministic State Machine**: Clear state transitions with timing rules
- **LLM-powered Responses**: Intelligent qualification with guardrails
- **Compliance Checks**: STOP words, prohibited content detection
- **Multi-channel Routing**: Email-first, SMS opt-in, manual escalation

### Scheduling
- Calendly integration
- Automated reminders (24h, 2h)
- No-show recovery
- Reschedule handling

### Analytics & Metrics
- **Real-time Metrics Dashboard**: View system stats via API endpoints
- **Apify Import Statistics**: Track run history, leads imported, duplicates skipped
- **Message Tracking**: Delivery, open, click rates via SendGrid webhooks
- **Suppression Tracking**: Bounces, complaints, unsubscribes logged automatically
- **Event Logging**: All state transitions, sends, and actions logged to `events` table
- **Revenue Attribution**: Track appointments → deals → commissions
- **Channel Performance**: Email vs SMS vs manual call effectiveness

**Metrics Storage:**
- All metrics stored in database (no external dashboard yet)
- Query via API endpoints or direct database access
- Use for debugging, reporting, and optimization decisions

## Inbound Reply Handling

The system automatically handles inbound email and SMS replies using GPT-4 with a hybrid AI-human approach.

### How It Works

1. **Inbound Message Received**: Email via SendGrid Inbound Parse or SMS via Twilio webhook
2. **AI Analysis**: GPT-4 classifies intent, calculates confidence, and generates response
3. **Decision Gate**: 
   - **Auto-Reply** if: High confidence (≥0.75), simple intent (interested/scheduling/FAQ), no compliance triggers
   - **Escalate** if: Low confidence, complex question, objection, complaint, or compliance-sensitive
4. **Action Taken**:
   - Auto-reply: Sends AI-generated response, updates conversation state
   - Escalate: Sends email notification to you, marks conversation as `NEEDS_HUMAN_REVIEW`
   - Unsubscribe: Automatically suppresses lead, sends confirmation

### Reply Categories

**Auto-Reply (60-70% of replies):**
- ✅ "Yes, I'm interested"
- ✅ "When can we talk?"
- ✅ "How long is the call?"
- ✅ "What is IUL?"
- ✅ "Stop emailing me" (auto-unsubscribe)

**Escalate to Human (30-40% of replies):**
- 🚨 "What's the guaranteed return?" (compliance trigger)
- 🚨 "Explain tax benefits vs 401k" (complex/advice)
- 🚨 "Not interested right now" (objection)
- 🚨 "This is harassment!" (complaint/threat)
- 🚨 Multiple questions (>2)

### Configuration

Add to `.env`:
```bash
# REQUIRED
OPENAI_API_KEY=sk-your-api-key-here
HUMAN_NOTIFICATION_EMAIL=your-email@example.com

# OPTIONAL (defaults shown)
REPLY_CONFIDENCE_THRESHOLD=0.75  # Lower = more escalations, Higher = more auto-replies
AUTO_REPLY_ENABLED=True
GPT4_MODEL=gpt-4-0125-preview
GPT4_TEMPERATURE=0.3
GPT4_MAX_TOKENS=300
```

### Escalation Email Format

When escalated, you'll receive an email with:
- 👤 Full lead information (name, company, email, phone, score)
- 💬 Their inbound message
- 🤖 AI analysis (intent, confidence, sentiment, escalation reason)
- 📜 Conversation history (last 5 messages)
- 💡 Recommended action from AI
- 🔗 Link to conversation dashboard

### Safety Features

- **Pre-Screening**: Fast detection of unsubscribe, threats, compliance keywords
- **Confidence Gating**: Only auto-replies when AI is confident
- **Sentiment Analysis**: Negative sentiment triggers escalation
- **Question Count**: Multiple questions (>2) trigger escalation
- **Compliance Checks**: Scans for prohibited content (guarantees, promises, advice)
- **Response Sanitization**: Removes/replaces prohibited phrases before sending
- **Double Validation**: AI responses checked for violations before sending

### Testing

```bash
# Test full system (requires OpenAI API key)
python scripts/test_reply_agent.py

# Test pre-screening only (no API calls)
python scripts/test_reply_agent.py --prescreening

# Test notification emails
python scripts/test_reply_agent.py --notification
```

### Cost Estimates

- **GPT-4 API**: ~$0.01 per inbound reply
- **1,000 replies/month**: ~$10
- **5,000 replies/month**: ~$50
- **10,000 replies/month**: ~$100

*Pre-screened messages (unsubscribe, threats) cost $0*

See `REPLY_AGENT_IMPLEMENTATION.md` for complete documentation.

## Compliance

The system includes built-in compliance features:
- **CAN-SPAM**: Physical address, unsubscribe links
- **TCPA**: SMS consent checks, STOP handling
- **Audit Logs**: All messages logged with timestamps
- **Inbound Reply Compliance**: No guarantees, no tax/legal advice, automatic escalation for risky content

## Testing Without Sending Emails (TEST_MODE)

Before you have all your API credentials set up, you can test the entire system without actually sending emails or SMS:

### Enable TEST_MODE

Add to your `.env` file:

```bash
# TEST MODE - Prevents actual email/SMS sends (logs only)
SENDGRID_TEST_MODE=True
TWILIO_TEST_MODE=True
```

### What TEST_MODE Does

**When enabled:**
- ✅ Lead processing: Works normally (imports, scoring, enrichment)
- ✅ Conversation workflow: State machine executes normally
- ✅ Message templates: Rendered and logged
- ✅ Database: All messages logged with `test_mode=True` flag
- ✅ Rate limiting: Still enforced (for realistic testing)
- ❌ Actual sends: NO emails or SMS sent to leads

**Log Output Example:**
```
🧪 TEST MODE: Would send email to lead@example.com
   Subject: Quick question about your insurance strategy
   Body preview: Hi John, saw you're the owner at ABC Law Firm...
✅ TEST MODE: Email logged (not sent) to lead@example.com
```

### Testing Strategy

1. **Import Test Leads**: Use a small CSV with fake/test leads
2. **Start System**: Run `python main.py` with `TEST_MODE=True`
3. **Watch Logs**: Monitor for `🧪 TEST MODE` messages
4. **Check Database**: Query messages table to see logged (not sent) messages
5. **Verify Workflow**: Confirm conversations move through states correctly

### When to Disable TEST_MODE

Only disable TEST_MODE when:
- ✅ SendGrid domain authenticated
- ✅ All API credentials configured
- ✅ Ready to send real emails to real leads
- ✅ Warmup schedule configured

```bash
# Ready for production
SENDGRID_TEST_MODE=False
TWILIO_TEST_MODE=False
```

## Development

### Running Tests

```bash
# Test Apify integration
python scripts/test_apify.py

# Test template variants
python scripts/test_templates.py

# Test inbound reply agent (requires OpenAI API key)
python scripts/test_reply_agent.py

# Test reply agent pre-screening only (no API calls)
python scripts/test_reply_agent.py --prescreening

# Test escalation notifications (requires SendGrid)
python scripts/test_reply_agent.py --notification

# Full test suite
pytest tests/
```

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

## Monitoring

View logs in real-time:

```bash
tail -f logs/system_*.log
```

Monitor Celery tasks:

```bash
celery -A src.workflow.celery_app inspect active
```

Check Apify import stats:

```
http://localhost:8000/api/sources/apify/stats
```

## System Orchestration

### Overview

The system operates autonomously through scheduled Celery tasks that coordinate lead acquisition, scoring, enrichment, and outbound messaging. All tasks respect rate limits, send windows, and warmup schedules.

### Key Design Principles

- **Warmup-Aware**: Lead acquisition scales with email volume (1.5x multiplier)
- **Rate-Limited**: All outbound sends respect daily/hourly caps and send windows
- **Batched Processing**: Conversations processed in batches for efficiency
- **State-Filtered**: Only processes conversations that need outbound messages
- **Quota-Managed**: Apify imports stop automatically when daily quota met
- **Parameter-Rotated**: Each Apify run uses different search parameters for diversity

## Scheduled Tasks

The system runs these tasks automatically via Celery Beat:

| Task | Frequency | Description |
|------|-----------|-------------|
| `run_apify_import` | Every 2 hours | Import new leads from Apify (runs up to `APIFY_MAX_RUNS_PER_TICK` times per tick until daily quota met) |
| `dispatch_outbound_messages` | Every 10 minutes | Process pending conversations (batched, respects rate limits & send window) |
| `score_unscored_leads` | Every 6 hours | Score any leads that don't have scores yet (safety net) |
| `enrich_high_priority_leads` | Daily at 2 AM UTC | Enrich tier 1-2 leads with website data |
| `send_24h_reminders` | Every 15 minutes | Send 24-hour appointment reminders |
| `send_2h_reminders` | Every 10 minutes | Send 2-hour appointment reminders |
| `check_no_shows` | Every 30 minutes | Mark no-shows and trigger recovery |

### Detailed Schedule Breakdown

**Lead Import (`run_apify_import`):**
- **Frequency:** Every 2 hours (during warmup) or 6 hours (post-warmup)
- **Per Tick:** Runs up to `APIFY_MAX_RUNS_PER_TICK` actor runs (default: 2)
- **Per Run:** ~100 leads (varies by actor)
- **Total Per Tick:** ~200 leads (with default 2 runs)
- **Daily Target:** Automatically calculated based on warmup schedule (daily_cap × 1.5)
- **Behavior:** Stops early when daily quota is met, skips weekends during warmup

**Outbound Messaging (`dispatch_outbound_messages`):**
- **Frequency:** Every 10 minutes
- **Batch Size:** Up to `SENDGRID_BATCH_SIZE` conversations per run (default: 20)
- **States Processed:** Only `NEW`, `CONTACTED`, `NO_RESPONSE` (filters out other states)
- **Send Window:** Mon-Fri, 8 AM-5 PM EST (skips outside window)
- **Rate Limits:** Enforces daily/hourly caps before sending
- **Per Conversation:** Sends opener → follow-up 1 (24h) → follow-up 2 (48h)

**Lead Scoring:**
- **New Leads:** Scored immediately during Apify import
- **Catch-up:** `score_unscored_leads` runs every 6 hours for any missed leads
- **Scoring Algorithm:** Weighted scoring based on industry, employee size, business age, location, contact quality

**Enrichment:**
- **Frequency:** Daily at 2 AM UTC
- **Target:** Tier 1-2 leads without enrichment
- **Purpose:** Scrapes company websites for personalization data
- **Usage:** Personalization bullets used in message templates (optional)

### Lead-to-Email Ratio

The system uses a **1.5x multiplier** for lead acquisition:
- **Formula:** `leads_needed = daily_email_cap × 1.5`
- **Rationale:** Accounts for scoring filters, duplicates, and already-contacted leads
- **Example:** 2,500 emails/day = 3,750 leads/day needed

This multiplier is optimized for Apollo data quality. Adjust if needed based on your actual deliverable rate.

### Conversation Messaging Schedule

**Per Lead Timeline:**
- **Opener:** Sent immediately when conversation created (next dispatcher tick within send window)
- **Follow-up #1:** Sent 24 hours after opener
- **Follow-up #2:** Sent 48 hours after opener (final automated follow-up)

**State Transitions:**
- `NEW` → `CONTACTED` (after opener sent)
- `CONTACTED` → `NO_RESPONSE` (after follow-up 1 sent)
- `NO_RESPONSE` → (waits for reply or manual close)

**Batching:**
- Processes up to `SENDGRID_BATCH_SIZE` conversations per 10-minute tick (default: 20)
- Only processes `NEW`, `CONTACTED`, `NO_RESPONSE` states
- Ordered by `next_action_at` (oldest first)
- Skips suppressed leads automatically

## Configuration

All configuration is centralized in `src/config.py` and loaded from environment variables. Key settings:

### Apify Lead Sourcing
- `APIFY_MAX_RUNS_PER_TICK`: Number of actor runs per 2-hour tick (default: 2)
- `APIFY_INDUSTRIES`: Comma-separated list of industries to target (default: law,accounting,medical,...)
- `APIFY_STATES`: Comma-separated list of states (default: Texas, United States,Florida, United States,...)
- `APIFY_EMPLOYEE_SIZES`: Comma-separated size ranges (default: 10-19,20-50,51-100,101-250,251-500)
- `APIFY_JOB_TITLES`: Comma-separated job titles (default: Owner,Managing Partner,Founder,CEO,...)
- `APIFY_API_TOKEN` through `APIFY_API_TOKEN_24`: Up to 24 Apify account tokens
- `APIFY_ACTOR_1` through `APIFY_ACTOR_24`: Up to 24 actor IDs

### Workflow
- `AUTO_START_CONVERSATIONS`: Automatically start conversations for tier 1-2 leads (default: True)
- `TIER_THRESHOLD_FOR_AUTO_START`: Max tier to auto-start (default: 2)
- `TEMPLATE_RANDOMIZATION`: Use template variants (default: True)

### SendGrid & Warmup
- `SENDGRID_WARMUP_MODE`: Enable warmup mode (default: True)
- `SENDGRID_DAILY_CAP`: Daily email cap (auto-managed by warmup, starts at 50)
- `SENDGRID_HOURLY_CAP`: Hourly email cap (default: 10)
- `SENDGRID_BATCH_SIZE`: Conversations processed per 10-minute tick (default: 20)
- `SENDGRID_SEND_START_HOUR`: Start of send window in EST (default: 8)
- `SENDGRID_SEND_END_HOUR`: End of send window in EST (default: 17)
- `SENDGRID_WEEKDAYS_ONLY`: Only send Mon-Fri (default: True)
- `WARMUP_MODE`: Enable warmup ramp (default: True)
- `WARMUP_START_DATE`: Go-live date in YYYY-MM-DD format (default: 2026-01-20)

## Support

For issues or questions, refer to the main project documentation.
