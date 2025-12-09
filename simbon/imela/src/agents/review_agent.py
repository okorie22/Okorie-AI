"""
Review Agent for ZerePy Content Pipeline
Sends clips for human review via email and handles approval/rejection
"""

import logging
import smtplib
import time
import imaplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from pathlib import Path
from typing import Dict, Any, Optional, List
import re
import sys
import os

# Import centralized configuration
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from config import REVIEW_CONFIG

logger = logging.getLogger("review_agent")


class ReviewAgent:
    """
    Sends edited clips for human review via email
    Listens for approval/rejection responses
    """
    
    def __init__(self, pipeline_manager, config_override: Optional[Dict[str, Any]] = None):
        """
        Initialize the Review Agent

        Args:
            pipeline_manager: ContentPipeline instance
            config_override: Optional config overrides
        """
        # Use centralized config with optional overrides
        config = REVIEW_CONFIG.copy()
        if config_override:
            config.update(config_override)

        self.pipeline_manager = pipeline_manager
        self.smtp_host = config["smtp_host"]
        self.smtp_port = config["smtp_port"]
        self.email_address = config["email_address"]
        self.email_password = config["email_password"]
        self.review_email = config["review_email"]
        self.timeout_hours = config["timeout_hours"]
        self.imap_host = config["imap_host"]
        self.email_subject_template = config["email_subject_template"]
        self.max_clips_per_email = config["max_clips_per_email"]
        self.approve_keywords = config["approve_keywords"]
        self.reject_keywords = config["reject_keywords"]

        # Create output directories
        self.review_pending_dir = Path(config["review_pending_dir"])
        self.review_pending_dir.mkdir(parents=True, exist_ok=True)

        # Track sent reviews
        self.pending_reviews = {}
        
        # Track sent reviews
        self.pending_reviews = {}  # video_id -> {sent_time, clip_ids}
        
        logger.info(f"Review Agent initialized")
        logger.info(f"  SMTP: {smtp_host}:{smtp_port}")
        logger.info(f"  Review email: {review_email}")
        logger.info(f"  Timeout: {timeout_hours}h")
    
    def send_for_review(self, video_id: str) -> bool:
        """
        Send clips for review via email
        
        Args:
            video_id: Pipeline video ID
            
        Returns:
            True if email sent successfully
        """
        try:
            logger.info(f"\n{'='*60}")
            logger.info(f"📧 REVIEW AGENT - SENDING FOR REVIEW")
            logger.info(f"{'='*60}")
            logger.info(f"Video ID: {video_id}")
            
            # Get pipeline status
            status = self.pipeline_manager.get_pipeline_status(video_id)
            if not status:
                logger.error("Video not found in pipeline")
                return False
            
            # Get edited clips
            clips = self.pipeline_manager.get_clips_for_video(video_id)
            if not clips:
                logger.error("No clips found for review")
                return False
            
            logger.info(f"Found {len(clips)} clips to review")
            
            # Compose email
            subject = f"🎬 New clips ready for review - {status['original_filename']}"
            body = self._compose_review_email(video_id, clips, status)
            
            # Send email
            logger.info(f"Sending review email to {self.review_email}...")
            success = self._send_email(subject, body)
            
            if success:
                # Update pipeline state
                from src.pipeline_manager import PipelineState
                self.pipeline_manager.update_state(video_id, PipelineState.REVIEW_PENDING)
                
                # Track pending review
                self.pending_reviews[video_id] = {
                    "sent_time": time.time(),
                    "clip_ids": [clip['clip_id'] for clip in clips]
                }
                
                logger.info(f"✅ Review email sent successfully")
                logger.info(f"{'='*60}\n")
                return True
            else:
                logger.error("Failed to send review email")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send for review: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _compose_review_email(self, video_id: str, clips: List[Dict],
                             status: Dict) -> str:
        """
        Compose the review email body
        
        Args:
            video_id: Video ID
            clips: List of clip dictionaries
            status: Pipeline status dictionary
            
        Returns:
            HTML email body
        """
        # Build email body
        body_parts = []
        
        body_parts.append("<html><body style='font-family: Arial, sans-serif;'>")
        body_parts.append(f"<h2>🎬 New Clips Ready for Review</h2>")
        body_parts.append(f"<p><strong>Video:</strong> {status['original_filename']}</p>")
        body_parts.append(f"<p><strong>Video ID:</strong> {video_id}</p>")
        body_parts.append(f"<p><strong>Created:</strong> {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(status['created_at']))}</p>")
        body_parts.append(f"<hr>")
        
        # Add clip details
        for i, clip in enumerate(clips, 1):
            body_parts.append(f"<h3>Clip {i}</h3>")
            body_parts.append(f"<p><strong>Clip ID:</strong> {clip['clip_id']}</p>")
            body_parts.append(f"<p><strong>Duration:</strong> {clip['duration']:.1f} seconds</p>")
            body_parts.append(f"<p><strong>Score:</strong> {clip.get('score', 0):.2f}/1.0</p>")
            
            if clip.get('transcript'):
                transcript = clip['transcript'][:200]
                if len(clip.get('transcript', '')) > 200:
                    transcript += "..."
                body_parts.append(f"<p><strong>Content:</strong> {transcript}</p>")
            
            # Add file path for manual review
            edited_path = clip.get('edited_path', clip.get('clip_path', 'N/A'))
            body_parts.append(f"<p><strong>File:</strong> <code>{edited_path}</code></p>")
            body_parts.append(f"<hr>")
        
        # Instructions
        body_parts.append(f"<h3>📝 How to Review:</h3>")
        body_parts.append(f"<ol>")
        body_parts.append(f"<li>Watch the clips at the file paths listed above</li>")
        body_parts.append(f"<li>Reply to this email with your decision:</li>")
        body_parts.append(f"<ul>")
        body_parts.append(f"<li>Type <strong>APPROVE {video_id}</strong> to approve and publish</li>")
        body_parts.append(f"<li>Type <strong>REJECT {video_id}</strong> to reject</li>")
        body_parts.append(f"<li>Or specify which clip: <strong>APPROVE CLIP {clips[0]['clip_id']}</strong></li>")
        body_parts.append(f"</ul>")
        body_parts.append(f"<li>If no response within {self.timeout_hours} hours, clips will be auto-rejected</li>")
        body_parts.append(f"</ol>")
        
        body_parts.append(f"<p><em>Note: You can also manually copy these files to post on Instagram.</em></p>")
        body_parts.append("</body></html>")
        
        return "".join(body_parts)
    
    def _send_email(self, subject: str, body: str) -> bool:
        """
        Send email via SMTP
        
        Args:
            subject: Email subject
            body: Email body (HTML)
            
        Returns:
            True if sent successfully
        """
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.email_address
            msg['To'] = self.review_email
            
            # Add HTML body
            html_part = MIMEText(body, 'html')
            msg.attach(html_part)
            
            # Send via SMTP
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_address, self.email_password)
                server.send_message(msg)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
    
    def check_for_responses(self) -> List[Dict[str, Any]]:
        """
        Check email for approval/rejection responses
        
        Returns:
            List of response dictionaries
        """
        try:
            logger.info("📬 Checking for review responses...")
            
            # Connect to IMAP
            mail = imaplib.IMAP4_SSL(self.imap_host)
            mail.login(self.email_address, self.email_password)
            mail.select('INBOX')
            
            # Search for unread emails from review email
            _, search_data = mail.search(None, 'UNSEEN', f'FROM "{self.review_email}"')
            
            responses = []
            
            for num in search_data[0].split():
                _, data = mail.fetch(num, '(RFC822)')
                msg = email.message_from_bytes(data[0][1])
                
                # Parse email
                subject = msg['subject']
                body = self._get_email_body(msg)
                
                # Look for approval/rejection keywords
                response = self._parse_response(body)
                
                if response:
                    responses.append(response)
                    logger.info(f"✅ Found response: {response['action']} for {response['video_id']}")
                    
                    # Process the response
                    self._process_response(response)
            
            mail.close()
            mail.logout()
            
            if responses:
                logger.info(f"Processed {len(responses)} response(s)")
            
            return responses
            
        except Exception as e:
            logger.error(f"Failed to check for responses: {e}")
            return []
    
    def _get_email_body(self, msg) -> str:
        """Extract email body from message"""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    return part.get_payload(decode=True).decode()
        else:
            return msg.get_payload(decode=True).decode()
        return ""
    
    def _parse_response(self, body: str) -> Optional[Dict[str, Any]]:
        """
        Parse approval/rejection from email body
        
        Args:
            body: Email body text
            
        Returns:
            Response dictionary or None if not a valid response
        """
        body_upper = body.upper()
        
        # Look for APPROVE/REJECT patterns
        approve_pattern = r'APPROVE\s+([a-f0-9\-]+)'
        reject_pattern = r'REJECT\s+([a-f0-9\-]+)'
        approve_clip_pattern = r'APPROVE\s+CLIP\s+([a-f0-9\-]+)'
        
        # Check for clip-specific approval
        match = re.search(approve_clip_pattern, body_upper)
        if match:
            clip_id = match.group(1).lower()
            return {
                "action": "approve",
                "video_id": None,  # Will need to look up
                "clip_id": clip_id,
                "specific_clip": True
            }
        
        # Check for video approval
        match = re.search(approve_pattern, body_upper)
        if match:
            video_id = match.group(1).lower()
            return {
                "action": "approve",
                "video_id": video_id,
                "clip_id": None,
                "specific_clip": False
            }
        
        # Check for video rejection
        match = re.search(reject_pattern, body_upper)
        if match:
            video_id = match.group(1).lower()
            return {
                "action": "reject",
                "video_id": video_id,
                "clip_id": None,
                "specific_clip": False
            }
        
        return None
    
    def _process_response(self, response: Dict[str, Any]):
        """
        Process an approval/rejection response
        
        Args:
            response: Response dictionary
        """
        try:
            action = response['action']
            video_id = response['video_id']
            clip_id = response.get('clip_id')
            
            # Get clips for video
            clips = self.pipeline_manager.get_clips_for_video(video_id)
            
            if not clips:
                logger.warning(f"No clips found for video {video_id}")
                return
            
            # Handle response
            if response['specific_clip']:
                # Approve specific clip
                clip = next((c for c in clips if c['clip_id'] == clip_id), None)
                if clip:
                    self.pipeline_manager.handle_review_response(
                        video_id, clip_id, approved=(action == "approve")
                    )
                    logger.info(f"✅ Clip {clip_id} {action}d")
            else:
                # Approve/reject all clips for video
                # For simplicity, approve the highest-scored clip
                if action == "approve" and clips:
                    best_clip = max(clips, key=lambda c: c.get('score', 0))
                    self.pipeline_manager.handle_review_response(
                        video_id, best_clip['clip_id'], approved=True
                    )
                    logger.info(f"✅ Video {video_id} approved (clip: {best_clip['clip_id']})")
                else:
                    # Reject all clips
                    for clip in clips:
                        self.pipeline_manager.handle_review_response(
                            video_id, clip['clip_id'], approved=False
                        )
                    logger.info(f"❌ Video {video_id} rejected")
            
            # Remove from pending reviews
            if video_id in self.pending_reviews:
                del self.pending_reviews[video_id]
                
        except Exception as e:
            logger.error(f"Failed to process response: {e}")
    
    def check_timeouts(self):
        """Check for pending reviews that have timed out"""
        try:
            current_time = time.time()
            timeout_seconds = self.timeout_hours * 3600
            
            timed_out = []
            
            for video_id, review_data in self.pending_reviews.items():
                elapsed = current_time - review_data['sent_time']
                
                if elapsed > timeout_seconds:
                    logger.warning(f"⏰ Review timeout for video {video_id}")
                    
                    # Auto-reject
                    for clip_id in review_data['clip_ids']:
                        self.pipeline_manager.handle_review_response(
                            video_id, clip_id, approved=False
                        )
                    
                    timed_out.append(video_id)
            
            # Remove timed out reviews
            for video_id in timed_out:
                del self.pending_reviews[video_id]
            
            if timed_out:
                logger.info(f"Auto-rejected {len(timed_out)} timed-out review(s)")
                
        except Exception as e:
            logger.error(f"Failed to check timeouts: {e}")

