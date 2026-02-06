"""
Human escalation notification system.
Sends email alerts when AI needs human review of a conversation.
"""
from typing import Dict, List, Optional
from loguru import logger
from datetime import datetime
import os

from ..storage.models import Conversation, Lead, Message


class NotificationService:
    """
    Sends notifications to human operators when conversations need review.
    """
    
    def __init__(self, db, config):
        """
        Initialize notification service.
        
        Args:
            db: Database session
            config: Settings object with notification settings
        """
        self.db = db
        self.notification_email = config.llm.human_notification_email
        self.sendgrid_config = config.sendgrid
        self.base_url = os.getenv("APP_BASE_URL", "http://localhost:8000")
    
    def send_escalation_email(
        self,
        conversation: Conversation,
        lead: Lead,
        inbound_message: str,
        analysis: Dict
    ) -> bool:
        """
        Send email notification about conversation requiring human review.
        
        Args:
            conversation: Conversation object
            lead: Lead object
            inbound_message: The message that triggered escalation
            analysis: AI analysis dict with intent, confidence, reason
        
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Build email content
            subject = self._build_subject(lead)
            body = self._build_body(
                conversation,
                lead,
                inbound_message,
                analysis
            )
            
            # Send via SendGrid
            success = self._send_email(
                to_email=self.notification_email,
                subject=subject,
                body=body
            )
            
            if success:
                logger.info(f"Escalation email sent for conversation {conversation.id}")
            else:
                logger.error(f"Failed to send escalation email for conversation {conversation.id}")
            
            return success
        
        except Exception as e:
            logger.error(f"Error sending escalation email: {e}", exc_info=True)
            return False
    
    def _build_subject(self, lead: Lead) -> str:
        """Build email subject line"""
        name = f"{lead.first_name} {lead.last_name}".strip() or "Unknown Lead"
        return f"[ACTION NEEDED] Lead Reply Requires Review - {name}"
    
    def _build_body(
        self,
        conversation: Conversation,
        lead: Lead,
        inbound_message: str,
        analysis: Dict
    ) -> str:
        """
        Build email body with all relevant information.
        
        Args:
            conversation: Conversation object
            lead: Lead object
            inbound_message: The message from prospect
            analysis: AI analysis results
        
        Returns:
            HTML email body
        """
        # Get conversation history
        messages = (
            self.db.query(Message)
            .filter(Message.conversation_id == conversation.id)
            .order_by(Message.created_at.desc())
            .limit(5)
            .all()
        )
        messages.reverse()  # Oldest first
        
        # Format conversation history
        history_html = "<ul style='font-family: monospace; font-size: 14px;'>"
        for msg in messages[:-1]:  # Exclude the latest (it's the inbound_message)
            direction = "➡️ You" if msg.direction.value == "outbound" else "⬅️ Prospect"
            timestamp = msg.created_at.strftime("%b %d, %I:%M %p") if msg.created_at else "N/A"
            history_html += f"<li><strong>{direction}</strong> ({timestamp}): {msg.body[:200]}</li>"
        history_html += "</ul>"
        
        # Lead score info
        score_info = "N/A"
        if lead.score:
            score_info = f"Tier {lead.score.tier} (Score: {lead.score.score}/100)"
        
        # Analysis details
        intent = analysis.get("intent", "unknown")
        confidence = analysis.get("confidence", 0.0)
        escalation_reason = analysis.get("escalation_reason", "Unknown reason")
        recommendation = analysis.get("recommendation", "Review and respond appropriately.")
        sentiment = analysis.get("sentiment", "neutral")
        
        # Build conversation URL
        conversation_url = f"{self.base_url}/messages?conversation_id={conversation.id}"
        
        # Build HTML email
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background-color: #ff6b6b;
            color: white;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
        .section {{
            background-color: #f8f9fa;
            padding: 15px;
            margin-bottom: 15px;
            border-radius: 5px;
            border-left: 4px solid #007bff;
        }}
        .lead-info {{
            background-color: #e8f4f8;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 15px;
        }}
        .message {{
            background-color: #fff;
            padding: 15px;
            border: 1px solid #dee2e6;
            border-radius: 5px;
            margin-bottom: 15px;
            font-size: 16px;
        }}
        .analysis {{
            background-color: #fff3cd;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 15px;
        }}
        .recommendation {{
            background-color: #d4edda;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 15px;
        }}
        .cta {{
            background-color: #007bff;
            color: white;
            padding: 12px 25px;
            text-decoration: none;
            border-radius: 5px;
            display: inline-block;
            margin-top: 15px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        td {{
            padding: 8px 0;
        }}
        .label {{
            font-weight: bold;
            width: 150px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h2 style="margin: 0;">🚨 Action Needed: Lead Reply Requires Review</h2>
    </div>
    
    <div class="lead-info">
        <h3 style="margin-top: 0;">Lead Information</h3>
        <table>
            <tr>
                <td class="label">Name:</td>
                <td>{lead.first_name} {lead.last_name}</td>
            </tr>
            <tr>
                <td class="label">Company:</td>
                <td>{lead.company_name or 'N/A'}</td>
            </tr>
            <tr>
                <td class="label">Industry:</td>
                <td>{lead.industry or 'N/A'}</td>
            </tr>
            <tr>
                <td class="label">Email:</td>
                <td><a href="mailto:{lead.email}">{lead.email}</a></td>
            </tr>
            <tr>
                <td class="label">Phone:</td>
                <td>{lead.phone or 'N/A'}</td>
            </tr>
            <tr>
                <td class="label">State:</td>
                <td>{lead.state or 'N/A'}</td>
            </tr>
            <tr>
                <td class="label">Lead Score:</td>
                <td>{score_info}</td>
            </tr>
            <tr>
                <td class="label">Conversation State:</td>
                <td>{conversation.state.value.upper()}</td>
            </tr>
        </table>
    </div>
    
    <div class="section">
        <h3 style="margin-top: 0;">Their Reply</h3>
        <div class="message">
            "{inbound_message}"
        </div>
    </div>
    
    <div class="analysis">
        <h3 style="margin-top: 0;">AI Analysis</h3>
        <table>
            <tr>
                <td class="label">Intent:</td>
                <td><strong>{intent.upper()}</strong></td>
            </tr>
            <tr>
                <td class="label">Confidence:</td>
                <td>{confidence:.1%}</td>
            </tr>
            <tr>
                <td class="label">Sentiment:</td>
                <td>{sentiment.capitalize()}</td>
            </tr>
            <tr>
                <td class="label">Escalation Reason:</td>
                <td>{escalation_reason}</td>
            </tr>
        </table>
    </div>
    
    <div class="section">
        <h3 style="margin-top: 0;">Conversation History</h3>
        {history_html}
    </div>
    
    <div class="recommendation">
        <h3 style="margin-top: 0;">💡 Recommended Action</h3>
        <p>{recommendation}</p>
    </div>
    
    <div style="text-align: center; margin-top: 30px;">
        <a href="{conversation_url}" class="cta">View Full Conversation</a>
    </div>
    
    <hr style="margin-top: 30px; border: none; border-top: 1px solid #dee2e6;">
    
    <p style="color: #6c757d; font-size: 14px; text-align: center;">
        <strong>Quick Reply Tip:</strong> You can reply directly to {lead.email} from your email client to continue the conversation.
        <br>The system will track your response automatically.
    </p>
</body>
</html>
"""
        
        return html_body
    
    def send_inbound_notification(
        self,
        lead: Lead,
        inbound_message: str,
        subject: str,
        conversation_id: int
    ) -> bool:
        """
        Send a simple notification when any inbound reply is received.
        
        Args:
            lead: Lead object
            inbound_message: The inbound message text
            subject: Email subject from the inbound
            conversation_id: Conversation ID
        
        Returns:
            True if sent successfully
        """
        try:
            name = f"{lead.first_name} {lead.last_name}".strip() or "Unknown Lead"
            email_subject = f"[NEW REPLY] {name} replied"
            
            conversation_url = f"{self.base_url}/messages?conversation_id={conversation_id}"
            
            body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background-color: #007bff;
            color: white;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
        .message {{
            background-color: #f8f9fa;
            padding: 15px;
            border-left: 4px solid #007bff;
            border-radius: 5px;
            margin: 15px 0;
        }}
        .cta {{
            background-color: #007bff;
            color: white;
            padding: 12px 25px;
            text-decoration: none;
            border-radius: 5px;
            display: inline-block;
            margin-top: 15px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h2 style="margin: 0;">💬 New Reply Received</h2>
    </div>
    
    <p><strong>From:</strong> {name} ({lead.email})</p>
    <p><strong>Company:</strong> {lead.company_name or 'N/A'}</p>
    <p><strong>Subject:</strong> {subject or '(no subject)'}</p>
    
    <div class="message">
        <strong>Their Message:</strong><br>
        {inbound_message[:500]}{"..." if len(inbound_message) > 500 else ""}
    </div>
    
    <div style="text-align: center; margin-top: 30px;">
        <a href="{conversation_url}" class="cta">View Full Conversation</a>
    </div>
    
    <hr style="margin-top: 30px; border: none; border-top: 1px solid #dee2e6;">
    
    <p style="color: #6c757d; font-size: 14px; text-align: center;">
        The AI is analyzing this message and will respond automatically if appropriate.
        <br>You'll receive an escalation alert if human review is needed.
    </p>
</body>
</html>
"""
            
            success = self._send_email(
                to_email=self.notification_email,
                subject=email_subject,
                body=body
            )
            
            if success:
                logger.info(f"Inbound notification sent for lead {lead.id}")
            
            return success
        
        except Exception as e:
            logger.error(f"Error sending inbound notification: {e}", exc_info=True)
            return False
    
    def _send_email(self, to_email: str, subject: str, body: str) -> bool:
        """
        Send email via SendGrid.
        
        Args:
            to_email: Recipient email
            subject: Email subject
            body: HTML email body
        
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail, Email, To, Content
            
            # Check if SendGrid is configured
            if not self.sendgrid_config.api_key:
                logger.error("SendGrid API key not configured")
                return False
            
            message = Mail(
                from_email=Email(
                    self.sendgrid_config.from_email,
                    self.sendgrid_config.from_name
                ),
                to_emails=To(to_email),
                subject=subject,
                html_content=Content("text/html", body)
            )
            
            sg = SendGridAPIClient(self.sendgrid_config.api_key)
            response = sg.send(message)
            
            if response.status_code in [200, 201, 202]:
                logger.info(f"Notification email sent to {to_email}")
                return True
            else:
                logger.error(f"SendGrid returned status {response.status_code}")
                return False
        
        except Exception as e:
            logger.error(f"Error sending email via SendGrid: {e}", exc_info=True)
            return False
    
    def send_test_notification(self, to_email: Optional[str] = None) -> bool:
        """
        Send a test notification to verify the system is working.
        
        Args:
            to_email: Optional override for recipient email
        
        Returns:
            True if sent successfully
        """
        recipient = to_email or self.notification_email
        
        subject = "[TEST] Escalation Notification System"
        ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        body = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }
        .header {
            background-color: #28a745;
            color: white;
            padding: 15px;
            border-radius: 5px;
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="header">
        <h2>Notification System Test</h2>
    </div>
    <p>This is a test notification from your IUL Appointment Setter system.</p>
    <p>If you're receiving this, your escalation notification system is configured correctly!</p>
    <p><strong>What this means:</strong></p>
    <ul>
        <li>SendGrid integration is working</li>
        <li>Notification email is correctly set</li>
        <li>You'll receive alerts when leads need your attention</li>
    </ul>
    <p style="color: #6c757d; font-size: 14px; margin-top: 30px;">
        Sent from: IUL Appointment Setter<br>
        Time: """ + ts + """
    </p>
</body>
</html>
"""
        
        return self._send_email(recipient, subject, body)
