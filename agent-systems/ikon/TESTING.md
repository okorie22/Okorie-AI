# IUL Pipeline Testing Guide

## Prerequisites

1. **Redis** must be running:
   ```bash
   redis-server
   ```

2. **Environment variables** in ITORO root `.env`:
   ```
   ELEVENLABS_API_KEY=your_key_here
   ELEVENLABS_VOICE_ID=your_voice_id_here
   REDIS_URL=redis://localhost:6379/0
   IUL_CTA_DOMAIN=https://yourdomain.com
   ```

3. **Remotion dependencies** installed:
   ```bash
   cd agent-systems/ikon/remotion
   npm install
   ```

4. **ffmpeg** installed (for audio duration and thumbnails)

## Manual Pipeline Testing

### Step 1: Load Test Idea
```python
from src.content.ideas_manager import IdeasManager, IdeaSchema
import json

# Load test idea
with open('data/ideas/test_idea.json', 'r') as f:
    idea_dict = json.load(f)

idea = IdeaSchema.from_dict(idea_dict)

# Save to ideas storage
manager = IdeasManager()
manager.save_idea(idea)

print(f"Test idea loaded: {idea.idea_id}")
```

### Step 2: Enqueue to Redis
```bash
# Using redis-cli
redis-cli LPUSH ikon:ideas:ready '{"job_id":"test_job_001","idea_id":"test_001","dedupe_key":"iul_basics_test_001","payload":{},"attempt":0,"max_attempts":3,"created_at":1737705600.0,"not_before":1737705600.0,"error_history":[]}'

# Or using Python
python -c "
from src.queue.redis_client import RedisQueueClient, create_job
import json

redis = RedisQueueClient()
with open('data/ideas/test_idea.json', 'r') as f:
    idea = json.load(f)

job = create_job('test_001', idea, 'iul_basics_test_001')
redis.enqueue('ideas:ready', job)
print(f'Job enqueued: {job.job_id}')
"
```

### Step 3: Run Pipeline Once
```bash
python -m src.pipeline.iul_pipeline_manager --once
```

### Step 4: Verify Outputs

Check each stage:

1. **Script generation**: Should see script logged with ~150 words
2. **Compliance check**: Should pass with score > 0.80
3. **Audio file**: `data/audio_cache/*.mp3` should exist
4. **Video file**: `data/rendered/*.mp4` should exist
5. **Thumbnail**: `data/rendered/*.jpg` should exist
6. **YouTube upload**: Check logs for video ID and URL

### Step 5: Check Queue Stats
```bash
redis-cli
> LLEN ikon:ideas:ready
> LLEN ikon:ideas:dead
> LRANGE ikon:ideas:ready 0 -1
```

## Testing Individual Components

### Script Composer
```python
from src.content.script_composer import ScriptComposer
from src.connections.deepseek_connection import DeepSeekConnection

deepseek = DeepSeekConnection({"model": "deepseek-chat"})
composer = ScriptComposer(deepseek)

# Load test idea
# ... (see above)

result = composer.compose_script(idea)
print(f"Script: {result['script']}")
print(f"Word count: {result['word_count']}")
print(f"Compliant: {result['compliance_hints']['appears_compliant']}")
```

### Compliance Check
```python
from src.agents.compliance_agent import ComplianceAgent

compliance = ComplianceAgent(platform="youtube", deepseek_connection=deepseek)

script = "..." # Your test script
result = compliance.check_script_compliance_iul(script)

print(f"Compliant: {result['compliant']}")
print(f"Score: {result['score']}")
print(f"Issues: {result['issues']}")
```

### TTS Generation
```python
from src.media.tts_elevenlabs import TTSService

tts_config = {
    "provider": "elevenlabs",
    "voice_id": "YOUR_VOICE_ID",
    "cache_enabled": True,
    "cache_dir": "data/audio_cache"
}

tts = TTSService(tts_config)
script = "..." # Your test script

audio_result = tts.generate_audio(script, "test_001")
print(f"Audio: {audio_result['audio_path']}")
print(f"Duration: {audio_result['duration']}s")
```

### Remotion Render
```python
from src.media.remotion_renderer import RemotionRenderer

remotion_config = {
    "project_dir": "remotion",
    "composition": "IULShortV1",
    "fps": 30,
    "width": 1080,
    "height": 1920
}

renderer = RemotionRenderer(remotion_config)

# Validate environment
checks = renderer.validate_environment()
print(f"Environment ready: {checks['ready']}")

# Render
props = {
    "hook": "Test hook",
    "bulletPoints": ["Point 1", "Point 2", "Point 3"],
    "cta": "Get the guide",
    "disclaimer": "Educational only..."
}

result = renderer.render_video("test_001", props, "path/to/audio.mp3")
print(f"Video: {result['video_path']}")
```

## Troubleshooting

### Redis not connecting
- Check Redis is running: `redis-cli ping` should return `PONG`
- Check REDIS_URL in .env matches your Redis instance

### ElevenLabs failing
- Verify API key is set: `echo $ELEVENLABS_API_KEY`
- Check voice_id is valid
- System will fallback to Edge TTS automatically

### Remotion render failing
- Run `npm install` in remotion directory
- Check Node.js version: `node --version` (needs v18+)
- Run `npx remotion preview` to test composition visually

### ffmpeg not found
- Install ffmpeg: https://ffmpeg.org/download.html
- Verify with: `ffmpeg -version`

## Expected Output

Successful pipeline run should produce:
```
✅ Script composed: 152 words, revised=False
✅ Script passed compliance (score: 0.87)
✅ ElevenLabs audio generated: data/audio_cache/abc123_test_001.mp3 (28.5s)
✅ Video rendered successfully: data/rendered/test_001_1737705600.mp4 (45.2s)
✅ Quick video check passed (30.0s)
✅ Published to YouTube Shorts: https://youtube.com/shorts/xyz123
✅ PIPELINE COMPLETED: test_001
```
