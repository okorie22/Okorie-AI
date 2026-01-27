"""
Message template rendering using variant data from template_variants.
Provides MessageTemplates for MessageSender (openers/follow-ups) and ReminderService.
"""
import random
from typing import Any, Dict, Optional, Tuple

from .template_variants import TEMPLATE_VARIANTS


def _template_context(
    lead: Any,
    enrichment: Optional[Any] = None,
    extra_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build placeholder dict for template format strings."""
    ctx = {
        "first_name": (getattr(lead, "first_name", None) or "there").strip() or "there",
        "industry": getattr(lead, "industry", None) or "",
        "company_name": getattr(lead, "company_name", None) or "",
        "calendly_link": getattr(lead, "calendly_link", None) or "",
        "previous_subject": getattr(lead, "previous_subject", None) or "quick question",
    }
    if enrichment is not None and hasattr(enrichment, "as_dict") and callable(enrichment.as_dict):
        ctx.update(enrichment.as_dict())
    elif enrichment is not None and isinstance(enrichment, dict):
        ctx.update(enrichment)
    if extra_context:
        ctx.update(extra_context)
    return ctx


def _fill(template: str, ctx: Dict[str, Any]) -> str:
    """Safe format: replace {key} with ctx[key], leave unknown keys as-is."""
    for k, v in ctx.items():
        template = template.replace("{" + str(k) + "}", str(v or ""))
    return template


class MessageTemplates:
    """
    Renders message templates with variant selection.
    Used by MessageSender (openers/follow-ups) and ReminderService.
    """

    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def render_with_variant(
        self,
        stage: str,
        lead: Any,
        conversation_id: Optional[int] = None,
        enrichment: Optional[Any] = None,
    ) -> Tuple[Dict[str, str], str]:
        """
        Pick a variant for the stage, fill placeholders, return (dict, variant_id).
        Dict has "subject" and "body" for email; SMS uses "body" only.
        """
        variants = TEMPLATE_VARIANTS.get(stage, [])
        if not variants:
            return ({"subject": "", "body": ""}, "")
        idx = random.randint(0, len(variants) - 1) if len(variants) > 1 else 0
        v = variants[idx]
        variant_id = v.get("id", "")
        ctx = _template_context(lead, enrichment=enrichment)
        body = _fill(v.get("body", ""), ctx)
        subject = _fill(v.get("subject", ""), ctx) if v.get("subject") else ""
        return ({"subject": subject, "body": body}, variant_id)

    def render(
        self,
        stage: str,
        lead: Any,
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        """
        Render a single template (e.g. reminders). Returns {"subject": ..., "body": ...}.
        Maps reminder stage names to template_variants keys where needed.
        """
        extra_context = extra_context or {}
        stage_map = {
            "reminder_24h_sms": "sms_reminder_24h",
            "reminder_2h_sms": "sms_reminder_2h",
        }
        actual_stage = stage_map.get(stage, stage)
        variants = TEMPLATE_VARIANTS.get(actual_stage, [])
        ctx = _template_context(lead, extra_context=extra_context)
        # Reminder templates use {time}; ReminderService passes appointment_time
        if "appointment_time" in extra_context and "time" not in ctx:
            ctx["time"] = extra_context["appointment_time"]
        if "meeting_url" in extra_context:
            ctx["meeting_url"] = extra_context["meeting_url"]
        if "calendly_link" not in ctx and "meeting_url" in ctx:
            ctx["calendly_link"] = ctx["meeting_url"]
        if not variants:
            if stage == "reminder_24h_email":
                appt = extra_context.get("appointment_time", "")
                url = extra_context.get("meeting_url", "")
                return {
                    "subject": "Reminder: call tomorrow",
                    "body": f"Hey {ctx['first_name']} — reminder: we have a call {appt}. Meeting link: {url}",
                }
            return {"subject": "", "body": ""}
        v = variants[0]
        return {
            "subject": _fill(v.get("subject", ""), ctx),
            "body": _fill(v.get("body", ""), ctx),
        }
