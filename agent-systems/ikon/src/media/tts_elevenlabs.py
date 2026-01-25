"""
TTS Service for IKON IUL Pipeline
Integrates ElevenLabs with caching, retry logic, and Edge TTS fallback
"""

import os
import hashlib
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional
import subprocess

logger = logging.getLogger("tts_service")


class TTSService:
    """Text-to-speech service with ElevenLabs and Edge TTS fallback"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize TTS service
        
        Args:
            config: TTS configuration from agent config
        """
        self.config = config
        self.provider = config.get("provider", "elevenlabs")
        self.voice_id = config.get("voice_id", "")
        self.model = config.get("model", "eleven_multilingual_v2")
        self.audio_format = config.get("audio_format", "mp3_44100_128")
        self.stability = config.get("stability", 0.5)
        self.similarity_boost = config.get("similarity_boost", 0.75)
        
        # Fallback config
        self.fallback_provider = config.get("fallback", {}).get("provider", "edge_tts")
        self.fallback_voice = config.get("fallback", {}).get("voice", "en-US-GuyNeural")
        
        # Caching
        self.cache_enabled = config.get("cache_enabled", True)
        cache_dir = config.get("cache_dir", "data/audio_cache")
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # API key
        self.api_key = os.getenv("ELEVENLABS_API_KEY", "")
        
        # Retry config
        self.max_retries = 3
        self.retry_delays = [2, 5, 10]
        
        logger.info(f"TTS service initialized: primary={self.provider}, fallback={self.fallback_provider}")
    
    def generate_audio(self, script: str, idea_id: str = None) -> Dict[str, Any]:
        """
        Generate audio from script
        
        Args:
            script: Script text to convert to speech
            idea_id: Optional idea identifier for filename
            
        Returns:
            {
                "audio_path": str,
                "duration": float,
                "provider": str,
                "voice_id": str,
                "cached": bool
            }
        """
        logger.info(f"Generating audio for script ({len(script)} chars)")
        
        # Check cache first
        if self.cache_enabled:
            cached_path = self._get_cached_audio(script)
            if cached_path:
                duration = self._get_audio_duration(cached_path)
                logger.info(f"✅ Using cached audio: {cached_path}")
                return {
                    "audio_path": str(cached_path),
                    "duration": duration,
                    "provider": "cache",
                    "voice_id": self.voice_id,
                    "cached": True
                }
        
        # Try ElevenLabs first
        if self.provider == "elevenlabs" and self.api_key:
            result = self._generate_elevenlabs(script, idea_id)
            if result:
                return result
            
            logger.warning("ElevenLabs generation failed, falling back to Edge TTS")
        
        # Fallback to Edge TTS
        result = self._generate_edge_tts(script, idea_id)
        if result:
            return result
        
        # Both failed
        raise Exception("All TTS providers failed")
    
    def _generate_elevenlabs(self, script: str, idea_id: str = None) -> Optional[Dict[str, Any]]:
        """Generate audio using ElevenLabs API"""
        try:
            from elevenlabs import generate, set_api_key, Voice, VoiceSettings
            
            set_api_key(self.api_key)
            
            logger.info("Generating audio with ElevenLabs...")
            
            # Configure voice settings
            voice_settings = VoiceSettings(
                stability=self.stability,
                similarity_boost=self.similarity_boost
            )
            
            # Retry loop
            for attempt in range(self.max_retries):
                try:
                    audio = generate(
                        text=script,
                        voice=Voice(
                            voice_id=self.voice_id,
                            settings=voice_settings
                        ),
                        model=self.model
                    )
                    
                    # Save audio
                    filename = self._generate_filename(script, idea_id, "elevenlabs")
                    audio_path = self.cache_dir / filename
                    
                    with open(audio_path, 'wb') as f:
                        for chunk in audio:
                            if isinstance(chunk, bytes):
                                f.write(chunk)
                            else:
                                f.write(chunk)
                    
                    duration = self._get_audio_duration(audio_path)
                    
                    logger.info(f"✅ ElevenLabs audio generated: {audio_path} ({duration:.1f}s)")
                    
                    return {
                        "audio_path": str(audio_path),
                        "duration": duration,
                        "provider": "elevenlabs",
                        "voice_id": self.voice_id,
                        "cached": False
                    }
                    
                except Exception as e:
                    if attempt < self.max_retries - 1:
                        delay = self.retry_delays[attempt]
                        logger.warning(f"ElevenLabs attempt {attempt + 1} failed: {e}, retrying in {delay}s...")
                        time.sleep(delay)
                    else:
                        raise
            
            return None
            
        except Exception as e:
            logger.error(f"ElevenLabs generation failed: {e}")
            return None
    
    def _generate_edge_tts(self, script: str, idea_id: str = None) -> Optional[Dict[str, Any]]:
        """Generate audio using Edge TTS (free fallback)"""
        try:
            logger.info("Generating audio with Edge TTS...")
            
            filename = self._generate_filename(script, idea_id, "edge_tts")
            audio_path = self.cache_dir / filename
            
            # Use edge-tts command line tool
            cmd = [
                "edge-tts",
                "--voice", self.fallback_voice,
                "--text", script,
                "--write-media", str(audio_path)
            ]
            
            # Retry loop
            for attempt in range(self.max_retries):
                try:
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=60,
                        check=True
                    )
                    
                    if audio_path.exists():
                        duration = self._get_audio_duration(audio_path)
                        logger.info(f"✅ Edge TTS audio generated: {audio_path} ({duration:.1f}s)")
                        
                        return {
                            "audio_path": str(audio_path),
                            "duration": duration,
                            "provider": "edge_tts",
                            "voice_id": self.fallback_voice,
                            "cached": False
                        }
                    else:
                        raise FileNotFoundError("Edge TTS did not create output file")
                        
                except subprocess.TimeoutExpired:
                    logger.warning(f"Edge TTS attempt {attempt + 1} timed out")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delays[attempt])
                    else:
                        raise
                except subprocess.CalledProcessError as e:
                    logger.warning(f"Edge TTS attempt {attempt + 1} failed: {e.stderr}")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delays[attempt])
                    else:
                        raise
            
            return None
            
        except Exception as e:
            logger.error(f"Edge TTS generation failed: {e}")
            return None
    
    def _get_cached_audio(self, script: str) -> Optional[Path]:
        """Check if audio is already cached"""
        cache_key = self._generate_cache_key(script)
        
        # Look for cached file
        for audio_file in self.cache_dir.glob(f"{cache_key}_*.mp3"):
            if audio_file.exists():
                return audio_file
        
        return None
    
    def _generate_cache_key(self, script: str) -> str:
        """Generate cache key from script"""
        # Hash script + voice settings for cache key
        content = f"{script}_{self.voice_id}_{self.provider}"
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    def _generate_filename(self, script: str, idea_id: str = None, provider: str = None) -> str:
        """Generate audio filename"""
        cache_key = self._generate_cache_key(script)
        timestamp = int(time.time())
        
        if idea_id:
            return f"{cache_key}_{idea_id}_{provider}_{timestamp}.mp3"
        else:
            return f"{cache_key}_{provider}_{timestamp}.mp3"
    
    def _get_audio_duration(self, audio_path: Path) -> float:
        """Get audio duration using ffprobe"""
        try:
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                str(audio_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
                check=True
            )
            
            import json
            data = json.loads(result.stdout)
            duration = float(data.get('format', {}).get('duration', 0))
            return duration
            
        except Exception as e:
            logger.warning(f"Failed to get audio duration: {e}")
            # Fallback estimate: ~150 words per minute
            # If we have script, estimate from word count
            return 30.0  # Default to 30s
    
    def clear_cache(self, older_than_days: int = 30) -> int:
        """
        Clear old cached audio files
        
        Args:
            older_than_days: Remove files older than this
            
        Returns:
            Number of files removed
        """
        cutoff_time = time.time() - (older_than_days * 24 * 3600)
        removed = 0
        
        for audio_file in self.cache_dir.glob("*.mp3"):
            if audio_file.stat().st_mtime < cutoff_time:
                audio_file.unlink()
                removed += 1
        
        if removed > 0:
            logger.info(f"Cleared {removed} cached audio files older than {older_than_days} days")
        
        return removed
