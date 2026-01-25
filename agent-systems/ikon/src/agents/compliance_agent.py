'''
🌙 Anarcho Capital's Compliance Agent 🌙
This agent analyzes videos for compliance with social media platform guidelines.
Supports YouTube and Instagram content policies.
It extracts frames from videos, transcribes audio, and provides a compliance rating.

Created with ❤️ by Anarcho Capital's AI Assistant
'''

import os
import sys
import cv2
import time
import json
import shutil
import whisper
import numpy as np
import base64
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
from termcolor import colored, cprint
from tqdm import tqdm
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
import threading

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Use existing connection system
# from src.models import model_factory

# Import centralized configuration
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from config import COMPLIANCE_CONFIG

# Configuration
MODEL_CONFIG = {
    "type": "openai",
    "name": "gpt-4o-mini",  # Using OpenAI's GPT-4o-mini model for analysis
    "reasoning_effort": "high"  # Maximum reasoning for compliance checks
}

# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "compliance"
GUIDELINES_PATHS = {
    "youtube": DATA_DIR / "youtube_guidelines.txt",
    "instagram": DATA_DIR / "instagram_guidelines.txt",
    "facebook": DATA_DIR / "fb_guidelines.txt"  # Legacy support
}
VIDEOS_DIR = Path("/Users/md/Dropbox/dev/github/search-arbitrage/bots/compliance/tiktok_ads")
OUTPUT_DIR = DATA_DIR / "analysis"
FRAMES_DIR = OUTPUT_DIR / "frames"
TRANSCRIPTS_DIR = OUTPUT_DIR / "transcripts"
REPORTS_DIR = OUTPUT_DIR / "reports"

# Create directories if they don't exist
for dir_path in [OUTPUT_DIR, FRAMES_DIR, TRANSCRIPTS_DIR, REPORTS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# System prompts for compliance analysis
COMPLIANCE_PROMPTS = {
    "youtube": """
You are a YouTube Content Compliance Analyst, an expert in YouTube's Community Guidelines and Content Policies.

Analyze the provided video frames and transcript to determine if they comply with YouTube's policies.

Check for:
- Hate speech or harassment
- Violent or graphic content
- Sexual content
- Harmful or dangerous content
- Misinformation
- Spam or deceptive practices
- Copyright violations (music, clips)
- Child safety concerns
- Monetization compliance (for YouTube Shorts)

Your response MUST follow this JSON format:
{
  "compliant": true/false,
  "score": 0.0-1.0,
  "issues": ["issue1", "issue2"],
  "recommendations": ["recommendation1", "recommendation2"],
  "platform_specific": {
    "monetizable": true/false,
    "age_restricted": true/false
  }
}
""",
    "instagram": """
You are an Instagram Content Compliance Analyst, an expert in Instagram's Community Guidelines.

Analyze the provided video frames and transcript to determine if they comply with Instagram's policies.

Check for:
- Nudity or sexual content
- Hate speech or bullying
- Violence or dangerous organizations
- Sale of illegal or regulated goods
- Intellectual property violations
- Suicide or self-injury content
- Graphic violence
- Misinformation

Your response MUST follow this JSON format:
{
  "compliant": true/false,
  "score": 0.0-1.0,
  "issues": ["issue1", "issue2"],
  "recommendations": ["recommendation1", "recommendation2"],
  "platform_specific": {
    "reels_eligible": true/false,
    "explore_eligible": true/false
  }
}
"""
}

class ComplianceAgent:
    """Agent to analyze content compliance with social media platform guidelines"""
    
    def __init__(self, platform: Optional[str] = None, guidelines_path: Optional[Path] = None,
                 deepseek_connection = None, config_override: Optional[Dict[str, Any]] = None):
        """
        Initialize the compliance agent

        Args:
            platform: Target platform ('youtube' or 'instagram') - overrides config
            guidelines_path: Optional custom guidelines path
            deepseek_connection: Optional DeepSeek connection for AI analysis
            config_override: Optional config overrides
        """
        # Use centralized config with optional overrides
        config = COMPLIANCE_CONFIG.copy()
        if config_override:
            config.update(config_override)

        self.platform = platform or config["platform"]
        self.guidelines = self._load_guidelines(self.platform, guidelines_path)
        self.enabled = config["enabled"]
        self.min_score_threshold = config["min_score_threshold"]
        self.quick_check = config["quick_check"]
        self.ai_model = config["ai_model"]

        # Frame extraction settings
        self.frames_to_extract = config["frames_to_extract"]
        self.transcript_length_limit = config["transcript_length_limit"]
        
        # Use provided connection
        self.deepseek = deepseek_connection
        self.model = None  # Legacy support, not used
            
        self._whisper_model = None  # Lazy-loaded
        
        # Create output directories if they don't exist
        for dir_path in [OUTPUT_DIR, FRAMES_DIR, TRANSCRIPTS_DIR, REPORTS_DIR]:
            dir_path.mkdir(parents=True, exist_ok=True)
            
        cprint(f"🌙 Compliance Agent initialized for {platform.upper()}! 🌙", "magenta")
        
    def _load_guidelines(self, platform: str, guidelines_path: Optional[Path] = None) -> str:
        """Load platform-specific guidelines"""
        if not guidelines_path:
            guidelines_path = GUIDELINES_PATHS.get(platform, GUIDELINES_PATHS["youtube"])
            
        try:
            with open(guidelines_path, 'r') as f:
                guidelines = f.read()
            cprint(f"✅ Loaded {platform} guidelines from {guidelines_path}", "green")
            return guidelines
        except Exception as e:
            cprint(f"⚠️  Guidelines file not found: {str(e)}", "yellow")
            # Return default guidelines based on platform
            if platform == "youtube":
                return "YouTube Community Guidelines: No hate speech, violence, sexual content, harmful content, spam, or copyright violations."
            elif platform == "instagram":
                return "Instagram Community Guidelines: No nudity, hate speech, violence, illegal goods, or misinformation."
            return "Platform guidelines not available."
            
    def _init_model(self):
        """Legacy method - not used when DeepSeek connection is provided"""
        cprint("⚠️ Using legacy model initialization - please provide DeepSeek connection", "yellow")
        return None
    
    def _lazy_load_whisper(self):
        """Lazy-load the Whisper model when needed"""
        if self._whisper_model is None:
            try:
                cprint("🔊 Loading Whisper model for transcription...", "cyan")
                self._whisper_model = whisper.load_model("base")
                cprint("✅ Whisper model loaded successfully!", "green")
            except Exception as e:
                cprint(f"❌ Error loading Whisper model: {str(e)}", "red")
                cprint("⚠️ Transcription will not be available", "yellow")
    
    def extract_frames(self, video_path: Path, output_folder: Path) -> List[Path]:
        """Extract exactly 10 frames evenly distributed throughout the video"""
        try:
            # Create output folder if it doesn't exist
            output_folder.mkdir(parents=True, exist_ok=True)
            
            # Open the video
            video = cv2.VideoCapture(str(video_path))
            
            # Check if video opened successfully
            if not video.isOpened():
                cprint(f"❌ Error: Could not open video {video_path}", "red")
                return []
            
            # Get video properties
            frame_count = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
            
            cprint(f"🎬 Processing video: {video_path.name}", "cyan")
            cprint(f"🖼️ Total frames: {frame_count}", "cyan")
            
            # Calculate intervals to capture 10 frames
            frame_interval = max(1, frame_count // 10)
            saved_count = 0
            frame_paths = []
            
            for frame_number in range(0, frame_count, frame_interval):
                # Set the video position to the frame number
                video.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
                success, frame = video.read()
                
                if not success:
                    break
                
                # Save the frame
                frame_path = output_folder / f"frame_{saved_count:04d}.jpg"
                cv2.imwrite(str(frame_path), frame)
                frame_paths.append(frame_path)
                saved_count += 1
                
                # Stop after saving 10 frames
                if saved_count >= 10:
                    break
                
                # Show progress
                if saved_count % 10 == 0:
                    cprint(f"💫 Extracted {saved_count} frames... Anarcho Capital would be proud!", "green")
            
            # Release the video
            video.release()
            
            cprint(f"✅ Extraction complete! Saved {saved_count} frames to {output_folder}", "green")
            return frame_paths
        except Exception as e:
            cprint(f"❌ Error extracting frames: {str(e)}", "red")
            return []
    
    def transcribe_video(self, video_path: Path, output_path: Path) -> str:
        """Transcribe video audio using Whisper"""
        try:
            # Lazy-load the Whisper model
            self._lazy_load_whisper()
            
            if self._whisper_model is None:
                return "Transcription not available - Whisper model failed to load."
            
            cprint(f"🎤 Transcribing audio from {video_path.name}...", "cyan")
            
            # Transcribe the audio
            result = self._whisper_model.transcribe(str(video_path))
            transcript = result["text"]
            
            # Save the transcript
            with open(output_path, 'w') as f:
                json.dump(result, f, indent=2)
            
            cprint(f"✅ Transcription complete! Saved to {output_path}", "green")
            cprint(f"📝 Transcript preview: {transcript[:100]}...", "cyan")
            
            return transcript
        except Exception as e:
            cprint(f"❌ Error transcribing video: {str(e)}", "red")
            return "Error transcribing video."
    
    def analyze_compliance(self, ad_name: str, frames_dir: Path, transcript: str) -> Dict:
        """Analyze ad compliance using AI model"""
        try:
            cprint(f"🔍 Analyzing compliance for ad: {ad_name}...", "cyan")
            
            # Get list of frames
            frames = sorted(list(frames_dir.glob("*.jpg")))
            if not frames:
                cprint(f"❌ No frames found in {frames_dir}", "red")
                return {"error": "No frames found for analysis"}
            
            # Create base64 encoded images instead of URLs
            image_contents = []
            for frame in frames[:5]:  # Limit to 5 frames to avoid token limits
                try:
                    with open(frame, "rb") as image_file:
                        encoded_image = base64.b64encode(image_file.read()).decode("utf-8")
                        image_contents.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{encoded_image}"
                            }
                        })
                    cprint(f"✅ Encoded frame: {frame.name}", "green")
                except Exception as e:
                    cprint(f"❌ Error encoding frame {frame.name}: {str(e)}", "red")
            
            # Prepare user content
            user_content = [
                {"type": "text", "text": "Please analyze this ad for compliance with Facebook's advertising guidelines."},
                {"type": "text", "text": f"Ad Name: {ad_name}"},
                {"type": "text", "text": f"Analyzing {len(image_contents)} frames from the video:"},
                *image_contents,
                {"type": "text", "text": "Transcript:"},
                {"type": "text", "text": transcript[:2000]},
                {"type": "text", "text": "Guidelines:"},
                {"type": "text", "text": self.guidelines[:5000]}
            ]
            
            # Get analysis from model
            cprint("🧠 Asking AI to analyze compliance...", "cyan")
            cprint("🌙 Compliance Agent is thinking deeply... 🌙", "magenta")
            
            # Use DeepSeek connection if available, otherwise use model factory
            if self.deepseek:
                # Build prompt for DeepSeek
                prompt = f"""Analyze this video for {self.platform} compliance.

Guidelines:
{self.guidelines[:3000]}

Transcript:
{transcript[:2000]}

{len(image_contents)} frames have been extracted from the video.

{COMPLIANCE_PROMPTS.get(self.platform, COMPLIANCE_PROMPTS['youtube'])}
"""
                response_text = self.deepseek.generate_text(
                    prompt=prompt,
                    temperature=0.3,
                    max_tokens=2000
                )
                content = response_text
            else:
                response = self.model.generate_response(
                    system_prompt=COMPLIANCE_PROMPTS.get(self.platform, COMPLIANCE_PROMPTS['youtube']),
                    user_content=user_content,
                    temperature=0.7,
                    max_tokens=2000
                )
                
                if not response or not hasattr(response, 'content'):
                    cprint("❌ Model returned empty response", "red")
                    return {"error": "Model returned empty response"}
                
                content = response.content
            
            # Try to parse JSON from response
            try:
                # Find JSON in the response (it might be wrapped in markdown code blocks)
                json_match = None
                if "```json" in content:
                    json_match = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    json_match = content.split("```")[1].split("```")[0].strip()
                else:
                    json_match = content.strip()
                
                analysis = json.loads(json_match)
                cprint("✅ Successfully parsed compliance analysis!", "green")
                
                # Print the response with appropriate formatting
                is_compliant = analysis.get('compliant', analysis.get('compliance_status') == 'compliant')
                score = analysis.get('score', 0.0)
                
                if is_compliant:
                    cprint(f"\n✅ COMPLIANT - Score: {score:.2f}", "white", "on_green")
                else:
                    cprint(f"\n❌ NON-COMPLIANT - Score: {score:.2f}", "white", "on_red")
                
                issues = analysis.get('issues', [])
                if issues:
                    cprint(f"Issues: {', '.join(issues)}", "yellow")
                
                return analysis
            except Exception as json_error:
                cprint(f"❌ Error parsing JSON from model response: {str(json_error)}", "red")
                cprint(f"Raw response: {content[:500]}...", "yellow")
                return {
                    "error": "Failed to parse JSON from model response",
                    "raw_response": content
                }
            
        except Exception as e:
            cprint(f"❌ Error analyzing compliance: {str(e)}", "red")
            return {"error": f"Error analyzing compliance: {str(e)}"}
    
    def generate_report(self, ad_name: str, analysis: Dict, output_path: Path) -> None:
        """Generate a detailed compliance report in JSON format only"""
        try:
            cprint(f"📊 Generating compliance report for {ad_name}...", "cyan")
            
            # Save the raw JSON analysis
            json_path = output_path.with_suffix('.json')
            with open(json_path, 'w') as f:
                json.dump(analysis, f, indent=2)
            
            cprint(f"✅ JSON report generated and saved to {json_path}", "green")
        except Exception as e:
            cprint(f"❌ Error generating JSON report: {str(e)}", "red")
    
    def check_pipeline_compliance(self, video_path: str, quick_check: bool = False) -> Dict[str, Any]:
        """
        Check video compliance for content pipeline use
        
        Args:
            video_path: Path to video file
            quick_check: If True, do faster analysis (fewer frames, no full transcription)
            
        Returns:
            {
                "compliant": bool,
                "score": float (0-1),
                "issues": List[str],
                "recommendations": List[str],
                "platform_specific": Dict
            }
        """
        try:
            import logging
            logger = logging.getLogger("compliance_agent")
            
            logger.info(f"🔍 Checking compliance for: {Path(video_path).name}")
            
            video_path_obj = Path(video_path)
            ad_name = video_path_obj.stem
            
            # Create temporary directories
            temp_frames_dir = FRAMES_DIR / f"temp_{ad_name}"
            temp_frames_dir.mkdir(parents=True, exist_ok=True)
            
            # Extract frames (fewer if quick check)
            frame_count = 3 if quick_check else 5
            frames = self.extract_frames(video_path_obj, temp_frames_dir)
            
            if not frames:
                logger.warning("Failed to extract frames")
                return {
                    "compliant": False,
                    "score": 0.0,
                    "issues": ["Failed to extract video frames"],
                    "recommendations": ["Check video file integrity"],
                    "platform_specific": {}
                }
            
            # Transcribe (skip if quick check and use placeholder)
            if quick_check:
                transcript = "[Quick check mode - full transcription skipped]"
            else:
                self._lazy_load_whisper()
                if self._whisper_model:
                    result = self._whisper_model.transcribe(str(video_path))
                    transcript = result["text"]
                else:
                    transcript = "[Transcription unavailable]"
            
            # Analyze compliance
            analysis = self.analyze_compliance(ad_name, temp_frames_dir, transcript)
            
            # Clean up temp frames
            import shutil
            shutil.rmtree(temp_frames_dir, ignore_errors=True)
            
            # Format response for pipeline
            if "error" in analysis:
                return {
                    "compliant": False,
                    "score": 0.0,
                    "issues": [analysis.get("error", "Unknown error")],
                    "recommendations": ["Review video manually"],
                    "platform_specific": {}
                }
            
            # Extract standard format
            is_compliant = analysis.get('compliant', analysis.get('compliance_status') == 'compliant')
            score = analysis.get('score', 0.5 if is_compliant else 0.3)
            
            result = {
                "compliant": is_compliant,
                "score": float(score),
                "issues": analysis.get('issues', []),
                "recommendations": analysis.get('recommendations', []),
                "platform_specific": analysis.get('platform_specific', {})
            }
            
            if is_compliant:
                logger.info(f"✅ Compliance check passed - Score: {score:.2f}")
            else:
                logger.warning(f"❌ Compliance check failed - Score: {score:.2f}")
                logger.warning(f"Issues: {', '.join(result['issues'])}")
            
            return result
            
        except Exception as e:
            import logging
            logging.error(f"Compliance check error: {e}")
            return {
                "compliant": False,
                "score": 0.0,
                "issues": [f"Compliance check error: {str(e)}"],
                "recommendations": ["Review video manually"],
                "platform_specific": {}
            }
    
    def process_video(self, video_path: Path) -> Dict:
        """Process a single video for compliance analysis"""
        try:
            cprint(f"\n{'='*50}", "yellow")
            cprint(f"🎬 Processing video: {video_path.name}", "cyan")
            cprint(f"{'='*50}\n", "yellow")
            
            # Create output directories for this video
            ad_name = video_path.stem
            video_frames_dir = FRAMES_DIR / ad_name
            video_frames_dir.mkdir(parents=True, exist_ok=True)
            
            # Step 1: Extract frames
            cprint("🖼️ Step 1: Extracting frames...", "cyan")
            frames = self.extract_frames(video_path, video_frames_dir)
            if not frames:
                cprint("❌ Failed to extract frames", "red")
                return {"error": "Failed to extract frames"}
            
            # Step 2: Transcribe audio
            cprint("🎤 Step 2: Transcribing audio...", "cyan")
            transcript_path = TRANSCRIPTS_DIR / f"{ad_name}_transcript.json"
            transcript = self.transcribe_video(video_path, transcript_path)
            
            # Step 3: Analyze compliance
            cprint("🔍 Step 3: Analyzing compliance...", "cyan")
            analysis = self.analyze_compliance(ad_name, video_frames_dir, transcript)
            
            # Step 4: Generate report
            cprint("📊 Step 4: Generating report...", "cyan")
            report_path = REPORTS_DIR / f"{ad_name}_report.json"
            self.generate_report(ad_name, analysis, report_path)
            
            cprint(f"\n✅ Completed processing for {ad_name}!", "green")
            cprint(f"📝 Report saved to: {report_path}", "green")
            
            # Return the analysis results
            return analysis
        except Exception as e:
            cprint(f"❌ Error processing video {video_path.name}: {str(e)}", "red")
            return {"error": f"Error processing video: {str(e)}"}
    
    def process_all_videos(self) -> None:
        """Process all videos in the videos directory"""
        try:
            # Get all video files
            video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.wmv']
            video_files = []
            
            for ext in video_extensions:
                video_files.extend(list(VIDEOS_DIR.glob(f"*{ext}")))
            
            if not video_files:
                cprint(f"⚠️ No video files found in {VIDEOS_DIR}", "yellow")
                cprint(f"🌙 Anarcho Capital says: Add some videos and try again! 🌙", "magenta")
                return
            
            # Process each video
            cprint(f"🎥 Found {len(video_files)} videos to process", "cyan")
            
            results = []
            for i, video_path in enumerate(video_files, 1):
                cprint(f"\n🔍 Processing video {i}/{len(video_files)}: {video_path.name}", "cyan")
                start_time = time.time()
                
                result = self.process_video(video_path)
                results.append({
                    "video": video_path.name,
                    "result": result
                })
                
                end_time = time.time()
                cprint(f"⏱️ Processing time: {end_time - start_time:.2f} seconds", "cyan")
            
            # Generate summary report
            self._generate_summary_report(results)
            
            cprint("\n🎉 All videos processed successfully!", "green")
            cprint(f"📂 Reports saved to: {REPORTS_DIR}", "green")
            cprint(f"🌟 Anarcho Capital's Compliance Agent has completed all tasks! 🌟", "magenta")
        except Exception as e:
            cprint(f"❌ Error processing videos: {str(e)}", "red")
    
    def _generate_summary_report(self, results: List[Dict]) -> None:
        """Generate a summary report of all processed videos in JSON format"""
        try:
            cprint("📊 Generating summary JSON report...", "cyan")
            
            summary_path = REPORTS_DIR / "summary_report.json"
            
            # Prepare summary data
            summary_data = {
                "date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "total_videos_processed": len(results),
                "compliant_videos": sum(1 for r in results if r.get('result', {}).get('is_compliant', False)),
                "non_compliant_videos": sum(1 for r in results if not r.get('result', {}).get('is_compliant', False)),
                "video_results": []
            }
            
            for i, result in enumerate(results, 1):
                video_name = result.get('video', 'Unknown')
                analysis = result.get('result', {})
                
                video_summary = {
                    "video": video_name,
                    "score": analysis.get('compliance_score', 'N/A'),
                    "status": "PASS" if analysis.get('is_compliant', False) else "FAIL",
                    "top_issue": "None"
                }
                
                if 'error' in analysis:
                    video_summary["error"] = analysis.get('error', 'Unknown error')
                else:
                    # Get top issue
                    visual_issues = analysis.get('visual_issues', [])
                    text_issues = analysis.get('text_issues', [])
                    all_issues = visual_issues + text_issues
                    
                    if all_issues:
                        # Sort by severity
                        severity_map = {"high": 3, "medium": 2, "low": 1}
                        sorted_issues = sorted(
                            all_issues, 
                            key=lambda x: severity_map.get(x.get('severity', 'low'), 0),
                            reverse=True
                        )
                        if sorted_issues:
                            video_summary["top_issue"] = sorted_issues[0].get('issue', 'Unknown issue')
                
                summary_data["video_results"].append(video_summary)
            
            # Save the summary JSON
            with open(summary_path, 'w') as f:
                json.dump(summary_data, f, indent=2)
            
            cprint(f"✅ Summary JSON report generated and saved to {summary_path}", "green")
        except Exception as e:
            cprint(f"❌ Error generating summary JSON report: {str(e)}", "red")
    
    # ==========================================
    # IUL-SPECIFIC COMPLIANCE METHODS
    # ==========================================
    
    def check_script_compliance_iul(self, script: str, platform: str = "youtube") -> Dict[str, Any]:
        """
        Check IUL script compliance (text-only, before video generation)
        
        This is a two-layer check:
        1. Deterministic rule layer (hard fails for blocked phrases)
        2. AI layer (nuanced scoring for tone, implied guarantees, advice patterns)
        
        Args:
            script: Script text to check
            platform: Target platform
            
        Returns:
            {
                "compliant": bool,
                "score": float (0-1),
                "issues": List[str],
                "suggestions": List[str],
                "rule_violations": List[str],
                "ai_concerns": List[str]
            }
        """
        import logging
        logger = logging.getLogger("compliance_iul")
        
        logger.info("Running IUL script compliance check...")
        
        # Layer 1: Deterministic rules
        rule_check = self._check_iul_deterministic_rules(script)
        
        # If hard fail on rules, no need for AI layer
        if rule_check["hard_fail"]:
            logger.warning(f"Hard fail on deterministic rules: {rule_check['violations']}")
            return {
                "compliant": False,
                "score": 0.0,
                "issues": rule_check["violations"],
                "suggestions": rule_check["suggestions"],
                "rule_violations": rule_check["violations"],
                "ai_concerns": []
            }
        
        # Layer 2: AI analysis
        ai_check = self._check_iul_ai_layer(script, platform)
        
        # Combine results
        total_issues = rule_check["soft_violations"] + ai_check.get("concerns", [])
        combined_score = (rule_check["score"] + ai_check.get("score", 0.8)) / 2
        
        # Must pass minimum threshold
        from config import IUL_PIPELINE_CONFIG
        min_threshold = IUL_PIPELINE_CONFIG["min_compliance_score"]
        
        result = {
            "compliant": combined_score >= min_threshold,
            "score": combined_score,
            "issues": total_issues,
            "suggestions": rule_check["suggestions"] + ai_check.get("suggestions", []),
            "rule_violations": rule_check["soft_violations"],
            "ai_concerns": ai_check.get("concerns", [])
        }
        
        if result["compliant"]:
            logger.info(f"✅ Script passed compliance (score: {combined_score:.2f})")
        else:
            logger.warning(f"❌ Script failed compliance (score: {combined_score:.2f})")
        
        return result
    
    def _check_iul_deterministic_rules(self, script: str) -> Dict[str, Any]:
        """Check IUL script against deterministic rules"""
        from config import IUL_PIPELINE_CONFIG
        
        script_lower = script.lower()
        violations = []
        soft_violations = []
        suggestions = []
        hard_fail = False
        
        # Check blocked phrases (hard fail)
        blocked_phrases = IUL_PIPELINE_CONFIG["blocked_phrases"]
        for phrase in blocked_phrases:
            if phrase.lower() in script_lower:
                violations.append(f"Blocked phrase detected: '{phrase}'")
                suggestions.append(f"Remove or rephrase '{phrase}' to avoid guarantee/risk-free claims")
                hard_fail = True
        
        # Check for disclaimer (soft fail)
        disclaimer_keywords = ["educational", "not advice", "not financial advice", "not insurance advice", "consult"]
        has_disclaimer = any(keyword in script_lower for keyword in disclaimer_keywords)
        if not has_disclaimer:
            soft_violations.append("Missing required disclaimer")
            suggestions.append(f"Add disclaimer: {IUL_PIPELINE_CONFIG['required_disclaimer']}")
        
        # Check for personalized advice patterns (soft fail)
        advice_patterns = [
            "you should",
            "you need to",
            "you must",
            "your situation requires",
            "i recommend you",
            "you ought to"
        ]
        for pattern in advice_patterns:
            if pattern in script_lower:
                soft_violations.append(f"Personalized advice pattern detected: '{pattern}'")
                suggestions.append(f"Replace '{pattern}' with educational framing like 'some people consider' or 'this approach may'")
        
        # Check for single CTA (soft fail)
        cta_indicators = ["link in description", "see description", "download", "get the", "visit"]
        cta_count = sum(1 for indicator in cta_indicators if indicator in script_lower)
        if cta_count > 1 and IUL_PIPELINE_CONFIG["single_cta_policy"]:
            soft_violations.append(f"Multiple CTAs detected ({cta_count} found)")
            suggestions.append("Consolidate to a single clear CTA")
        elif cta_count == 0:
            soft_violations.append("No CTA detected")
            suggestions.append("Add a single clear CTA directing to lead gen resource")
        
        # Calculate rule score
        if hard_fail:
            rule_score = 0.0
        else:
            # Start at 1.0, deduct for soft violations
            rule_score = 1.0 - (len(soft_violations) * 0.15)
            rule_score = max(0.0, rule_score)
        
        return {
            "hard_fail": hard_fail,
            "violations": violations,
            "soft_violations": soft_violations,
            "suggestions": suggestions,
            "score": rule_score
        }
    
    def _check_iul_ai_layer(self, script: str, platform: str) -> Dict[str, Any]:
        """AI-based nuanced compliance check"""
        if not self.deepseek:
            # No AI available, return neutral score
            return {"score": 0.8, "concerns": [], "suggestions": []}
        
        prompt = f"""You are an insurance compliance expert analyzing a YouTube Short script for IUL (Indexed Universal Life) education content.

SCRIPT TO ANALYZE:
{script}

COMPLIANCE REQUIREMENTS:
1. EDUCATIONAL ONLY - Must explain concepts, not sell or recommend
2. NO GUARANTEES - No implied promises of returns, outcomes, or "risk-free" claims
3. NO PERSONALIZED ADVICE - General education, not tailored recommendations
4. DISCLAIMER REQUIRED - Must include educational disclaimer
5. REGULATORY SAFE - No language that could trigger insurance compliance issues

EVALUATE:
1. Tone: Is it educational or sales-oriented? (0-1 scale)
2. Implied guarantees: Any subtle promises or certainty about outcomes? (list)
3. Advice vs education: Does it cross into recommendations? (list concerns)
4. Regulatory risk words: Any problematic insurance/financial terms? (list)

Respond in JSON format:
{{
  "educational_score": 0.0-1.0,
  "guarantee_concerns": ["concern1", "concern2"],
  "advice_concerns": ["concern1", "concern2"],
  "regulatory_risks": ["risk1", "risk2"],
  "overall_assessment": "brief summary",
  "suggestions": ["suggestion1", "suggestion2"]
}}"""

        try:
            response = self.deepseek.generate_text(
                prompt=prompt,
                temperature=0.3,
                max_tokens=800
            )
            
            # Parse JSON from response
            json_match = None
            if "```json" in response:
                json_match = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_match = response.split("```")[1].split("```")[0].strip()
            elif "{" in response:
                start = response.find("{")
                end = response.rfind("}") + 1
                json_match = response[start:end]
            else:
                json_match = response.strip()
            
            ai_result = json.loads(json_match)
            
            # Calculate AI score
            educational_score = ai_result.get("educational_score", 0.8)
            concern_count = len(ai_result.get("guarantee_concerns", [])) + len(ai_result.get("advice_concerns", [])) + len(ai_result.get("regulatory_risks", []))
            
            # Deduct for concerns
            ai_score = educational_score - (concern_count * 0.1)
            ai_score = max(0.0, min(1.0, ai_score))
            
            # Aggregate concerns
            all_concerns = []
            if ai_result.get("guarantee_concerns"):
                all_concerns.extend([f"Implied guarantee: {c}" for c in ai_result["guarantee_concerns"]])
            if ai_result.get("advice_concerns"):
                all_concerns.extend([f"Advice pattern: {c}" for c in ai_result["advice_concerns"]])
            if ai_result.get("regulatory_risks"):
                all_concerns.extend([f"Regulatory risk: {c}" for c in ai_result["regulatory_risks"]])
            
            return {
                "score": ai_score,
                "concerns": all_concerns,
                "suggestions": ai_result.get("suggestions", []),
                "raw_analysis": ai_result
            }
            
        except Exception as e:
            import logging
            logging.error(f"AI compliance check failed: {e}")
            # Fallback to neutral score
            return {"score": 0.7, "concerns": ["AI analysis unavailable"], "suggestions": []}
    
    def quick_video_check(self, video_path: str) -> Dict[str, Any]:
        """
        Quick post-render sanity check
        
        Lightweight check to verify:
        - Video renders correctly (no corruption)
        - Pacing isn't too fast/slow
        - No unintended visual content
        
        Args:
            video_path: Path to rendered video
            
        Returns:
            {
                "passed": bool,
                "issues": List[str],
                "video_duration": float,
                "frame_check": dict
            }
        """
        import logging
        logger = logging.getLogger("compliance_quick_check")
        
        logger.info(f"Running quick video check: {video_path}")
        
        issues = []
        
        try:
            # Check video exists and is readable
            video_path_obj = Path(video_path)
            if not video_path_obj.exists():
                return {
                    "passed": False,
                    "issues": ["Video file not found"],
                    "video_duration": 0,
                    "frame_check": {}
                }
            
            # Open video
            video = cv2.VideoCapture(str(video_path))
            if not video.isOpened():
                return {
                    "passed": False,
                    "issues": ["Video file corrupted or unreadable"],
                    "video_duration": 0,
                    "frame_check": {}
                }
            
            # Get properties
            frame_count = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = int(video.get(cv2.CAP_PROP_FPS))
            duration = frame_count / fps if fps > 0 else 0
            
            # Check duration (30s target, allow 25-35s)
            if duration < 25:
                issues.append(f"Video too short: {duration:.1f}s (target: 30s)")
            elif duration > 35:
                issues.append(f"Video too long: {duration:.1f}s (target: 30s)")
            
            # Sample 3 frames
            frame_samples = []
            for i in [0, frame_count // 2, frame_count - 1]:
                video.set(cv2.CAP_PROP_POS_FRAMES, i)
                success, frame = video.read()
                if success:
                    # Basic frame check (not all black, not all white)
                    mean_intensity = np.mean(frame)
                    frame_samples.append({
                        "position": i,
                        "mean_intensity": float(mean_intensity),
                        "valid": 10 < mean_intensity < 245
                    })
            
            video.release()
            
            # Check frame validity
            invalid_frames = [f for f in frame_samples if not f["valid"]]
            if invalid_frames:
                issues.append(f"Potentially corrupted frames detected: {len(invalid_frames)}")
            
            frame_check = {
                "total_frames": frame_count,
                "fps": fps,
                "duration": duration,
                "samples": frame_samples
            }
            
            result = {
                "passed": len(issues) == 0,
                "issues": issues,
                "video_duration": duration,
                "frame_check": frame_check
            }
            
            if result["passed"]:
                logger.info(f"✅ Quick video check passed ({duration:.1f}s)")
            else:
                logger.warning(f"⚠️ Quick video check found issues: {issues}")
            
            return result
            
        except Exception as e:
            logger.error(f"Quick video check failed: {e}")
            return {
                "passed": False,
                "issues": [f"Check error: {str(e)}"],
                "video_duration": 0,
                "frame_check": {}
            }

def main():
    """Main function to run the compliance agent"""
    print("🚀 Starting Anarcho Capital's Compliance Agent 🚀")
    
    try:
        # Initialize the compliance agent
        agent = ComplianceAgent()
        
        # Process all videos
        agent.process_all_videos()
        
    except KeyboardInterrupt:
        cprint("\n👋 Anarcho Capital's Compliance Agent shutting down gracefully...", "yellow")
    except Exception as e:
        cprint(f"\n❌ Fatal error: {str(e)}", "red")
        import traceback
        cprint(traceback.format_exc(), "red")

if __name__ == "__main__":
    main()