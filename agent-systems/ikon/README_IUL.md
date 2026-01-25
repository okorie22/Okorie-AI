# IUL Lead Generation YouTube Automation System

Complete automated system for creating and publishing compliant IUL education YouTube Shorts with lead generation optimization.

## System Overview

This system operates in two modes:

### Mode A: Content Pipeline (iul_generation)
Automated video creation from idea → published Short with compliance gates and lead-gen optimization.

**Flow**: Ideas → Script Composer → IUL Compliance → TTS (ElevenLabs) → Remotion Render → Post-Render Check → YouTube Upload → Engagement Seed

### Mode B: Autonomous Intelligence (scheduler-based)
Continuous data gathering, idea generation, and engagement management.

**Flow**: Analytics Gathering → Competitor Monitoring → Search Insights → Research Agent → Idea Generation → Queue to Pipeline + Comment Management

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Content Pipeline                       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Redis Queue → Script → Compliance → TTS → Remotion     │
│                         Gate                             │
│               → Post Check → Publish → YouTube           │
│                                                          │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                 Autonomous Intelligence                  │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐ │
│  │  Analytics  │  │ Competitors  │  │    Search      │ │
│  │  Gatherer   │  │   Analyzer   │  │   Insights     │ │
│  └──────┬──────┘  └──────┬───────┘  └────────┬───────┘ │
│         │                │                    │         │
│         └────────────────┼────────────────────┘         │
│                          ▼                               │
│                  ┌───────────────┐                      │
│                  │ Research Agent│                      │
│                  └───────┬───────┘                      │
│                          │                               │
│                          ▼                               │
│                  [ Ideas Queue ]                         │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## Components

### Core Pipeline
- **Redis Queue Client** (`src/queue/redis_client.py`): Job queuing with retry logic and DLQ
- **Ideas Manager** (`src/content/ideas_manager.py`): JSONL-based idea storage and tracking
- **Script Composer** (`src/content/script_composer.py`): AI-powered script generation with 2nd draft logic
- **IUL Compliance Agent** (`src/agents/compliance_agent.py`): Two-layer compliance checking (deterministic + AI)
- **TTS Service** (`src/media/tts_elevenlabs.py`): ElevenLabs TTS with Edge TTS fallback and caching
- **Remotion Renderer** (`src/media/remotion_renderer.py`): Python bridge to Remotion CLI for video generation
- **Publishing Agent** (`src/agents/publishing_agent.py`): YouTube upload with lead-gen metadata and UTM tracking
- **Pipeline Orchestrator** (`src/pipeline/iul_pipeline_manager.py`): State machine managing end-to-end workflow

### Intelligence Gathering
- **Analytics Gatherer** (`src/intel/analytics_gatherer.py`): Channel/video stats with quota-aware sampling
- **Competitor Analyzer** (`src/intel/competitor_analyzer.py`): Monitor competitor channels for trending topics
- **Search Insights** (`src/intel/search_insights.py`): Google Trends + YouTube autocomplete research

### Autonomous Agents
- **Research Agent** (`src/agents/research_agent.py`): Generates scored ideas from intelligence data
- **Engagement Manager** (`src/agents/engagement_manager.py`): Comment classification and auto-replies

### Remotion Templates
- **IULShortV1** (`remotion/src/compositions/IULShortV1.tsx`): 30-second vertical video template
  - Hook Scene (0-2s): Big, bold opening
  - Value Scene (2-24s): 3 bullet points with icons
  - CTA Scene (24-30s): Call-to-action with disclaimer

## Installation

### Prerequisites
- Python 3.10+
- Node.js 18+
- Redis server
- ffmpeg
- ElevenLabs API key

### Setup

1. **Install Python dependencies:**
```bash
cd agent-systems/ikon
pip install -r requirements.txt
```

2. **Install Remotion dependencies:**
```bash
cd remotion
npm install
```

3. **Configure environment variables** (in ITORO root `.env`):
```
ELEVENLABS_API_KEY=your_key_here
ELEVENLABS_VOICE_ID=your_voice_id_here
REDIS_URL=redis://localhost:6379/0
IUL_CTA_DOMAIN=https://yourdomain.com
YOUTUBE_API_KEY=your_youtube_key
DEEPSEEK_API_KEY=your_deepseek_key
```

4. **Start Redis:**
```bash
redis-server
```

5. **Update competitor list** in `config.py`:
```python
IUL_INTEL_CONFIG = {
    "competitors": [
        {"channel_id": "UCxxxxx", "label": "Competitor1", "priority": "high"},
        {"channel_id": "UCyyyyy", "label": "Competitor2", "priority": "medium"},
    ],
    # ...
}
```

## Usage

### Manual Pipeline Testing

See `TESTING.md` for detailed testing guide.

**Quick start:**

1. Load test idea:
```python
from src.content.ideas_manager import IdeasManager, IdeaSchema
import json

with open('data/ideas/test_idea.json') as f:
    idea = IdeaSchema.from_dict(json.load(f))

manager = IdeasManager()
manager.save_idea(idea)
```

2. Enqueue to Redis:
```bash
python -c "
from src.queue.redis_client import RedisQueueClient, create_job
import json

redis = RedisQueueClient()
with open('data/ideas/test_idea.json') as f:
    idea = json.load(f)

job = create_job('test_001', idea, 'iul_test_001')
redis.enqueue('ideas:ready', job)
print(f'Enqueued: {job.job_id}')
"
```

3. Run pipeline once:
```bash
python -m src.pipeline.iul_pipeline_manager --once
```

### Autonomous Mode

Run the YouTube manager agent for continuous operation:

```bash
python main.py youtube_manager
```

This will:
- Gather analytics every 30 minutes
- Monitor competitors every 6 hours
- Check search trends every 12 hours
- Generate ideas every 4 hours
- Process comments every 30 minutes
- Auto-enqueue high-scoring ideas to pipeline

## Configuration

### IUL Compliance Rules (`config.py`)

```python
IUL_PIPELINE_CONFIG = {
    "blocked_phrases": [
        "guaranteed", "risk-free", "no risk", 
        "tax-free retirement guaranteed", "beats the market"
    ],
    "required_disclaimer": "Educational only. Not financial/insurance advice...",
    "min_compliance_score": 0.80,
    "target_word_count": 150
}
```

### Intelligence Gathering Cadence

```python
IUL_INTEL_CONFIG = {
    "gather_cadence": {
        "analytics": 1800,      # 30 minutes
        "competitors": 21600,   # 6 hours
        "search": 43200         # 12 hours
    }
}
```

## Data Storage

```
data/
├── ideas/
│   └── ideas.jsonl              # All ideas (JSONL format)
├── audio_cache/
│   └── *.mp3                    # Cached TTS audio
├── rendered/
│   ├── *.mp4                    # Rendered videos
│   └── *.jpg                    # Thumbnails
├── intel/
│   ├── analytics_history.jsonl
│   ├── competitor_snapshots.jsonl
│   └── search_trends.json
├── engagement/
│   └── review_queue.json        # High-risk comments for human review
└── iul_pipeline.db              # Pipeline state tracking
```

## Compliance Strategy

### Two-Layer Compliance Check

**Layer 1: Deterministic Rules**
- Blocked phrases (hard fail)
- Disclaimer presence
- Personalized advice patterns
- Single CTA policy

**Layer 2: AI Analysis**
- Educational vs sales tone scoring
- Implied guarantee detection
- Regulatory risk assessment

**Minimum Score**: 0.80 (combined layers)

### Post-Render Check
- Video integrity verification
- Duration check (25-35s)
- Frame corruption detection

## Lead Generation Strategy

### Single CTA Focus
- One clear call-to-action per video
- UTM tracking: `utm_source=youtube&utm_medium=shorts&utm_content={idea_id}`
- Description format: Value prop → Disclaimer → CTA link → Hashtags

### Metadata Optimization
- Title: Hook-based, <100 chars, curiosity-driven
- Description: Educational framing with single CTA
- Tags: IUL-relevant keywords from idea

### Engagement Management
- **Low Risk**: Auto-reply with educational responses
- **Medium/High Risk**: Escalate to human review queue
- Never provide personalized advice or quotes

## Monitoring

### Queue Stats
```bash
redis-cli
> LLEN ikon:ideas:ready      # Ideas waiting
> LLEN ikon:ideas:dead        # Failed jobs
> LRANGE ikon:ideas:ready 0 -1  # View queue
```

### Pipeline Status
```python
from src.pipeline.iul_pipeline_manager import IULPipelineManager

# ... initialize manager ...
active_runs = manager.get_active_runs()
print(f"Active runs: {len(active_runs)}")
```

### Analytics
Check `data/intel/` for gathered intelligence:
- `analytics_history.jsonl`: Channel performance over time
- `competitor_snapshots.jsonl`: Competitor trending topics
- `search_trends.json`: Google Trends + YouTube autocomplete data

## Error Handling

### Job Retry Strategy
- Max 3 attempts per stage
- Exponential backoff: 60s, 300s, 900s
- DLQ after max attempts with full error context

### API Rate Limits
- YouTube quota tracking (daily 10K limit)
- ElevenLabs character limits
- Graceful degradation on quota exhaustion

### Compliance Failures
- Log rejection reason with suggestions
- Optional single auto-revision attempt
- Manual review queue for borderline cases

## Remotion Development

Preview composition visually:
```bash
cd remotion
npm run remotion preview
```

Customize brand theme in `remotion/src/theme.ts`:
```typescript
export const theme = {
    colors: {
        primary: '#FFFFFF',
        accent: '#00D084',
        background: '#0B0F1A'
    },
    // ...
}
```

## Troubleshooting

### Redis Connection Failed
```bash
# Check Redis is running
redis-cli ping  # Should return PONG

# Verify REDIS_URL in .env
echo $REDIS_URL
```

### ElevenLabs Failing
- Verify API key: `echo $ELEVENLABS_API_KEY`
- Check voice_id is valid
- System falls back to Edge TTS automatically

### Remotion Render Failing
```bash
# Check Node.js version
node --version  # Should be v18+

# Install dependencies
cd remotion && npm install

# Test composition visually
npm run remotion preview
```

### ffmpeg Not Found
- Install: https://ffmpeg.org/download.html
- Verify: `ffmpeg -version`

## Performance Metrics

Track in ideas.jsonl:
- `published_at`: Publication timestamp
- `youtube_video_id`: Video identifier
- `utm_content`: UTM tracking parameter

Query YouTube Analytics API (48h post-publish) for:
- Views, CTR, avg_view_duration, traffic_sources

Feed high-performing topics/hooks back to research agent for optimization.

## Architecture Decisions

### Why JSONL for Ideas?
- Append-only (safe for concurrent writes)
- Easy to grep/parse
- Human-readable for debugging

### Why Redis?
- Fast job queuing with blocking dequeue
- Native support for retry logic
- DLQ pattern for failed jobs

### Why Remotion?
- Programmatic video generation (no manual editing)
- React-based (familiar for developers)
- Template consistency across all Shorts

### Why Two-Layer Compliance?
- Deterministic rules catch obvious violations (fast)
- AI layer catches nuanced compliance issues
- Combined approach balances speed and accuracy

## Contributing

When adding new idea generation logic:
1. Extend `research_agent._score_idea()` with new scoring metrics
2. Update `IUL_PIPELINE_CONFIG` with new compliance rules
3. Add tests in `TESTING.md` workflow

When adding new Remotion templates:
1. Create composition in `remotion/src/compositions/`
2. Register in `remotion/src/Root.tsx`
3. Update `remotion_renderer.py` with new composition ID

## License

See LICENSE file in project root.

## Support

For issues or questions:
1. Check `TESTING.md` for debugging steps
2. Review logs in `data/` directories
3. Check Redis queue status
4. Inspect pipeline state in `iul_pipeline.db`
