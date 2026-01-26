"""
Template variants for human-like messaging.
Multiple versions per stage to avoid repetition and spam detection.
"""

# Email opener variants - casual, low-hype, single question
OPENER_EMAIL_VARIANTS = [
    {
        "id": "opener_email_v1",
        "subject": "quick question",
        "body": """Hey {first_name} —

Do you handle your own retirement planning or do you have someone you trust for that?

If you're open, I can share a quick idea that's working for a few business owners I've been talking to.

Worth a 20–30 min call this week?"""
    },
    {
        "id": "opener_email_v2",
        "subject": "retirement planning",
        "body": """{first_name}, curious —

Do you have a strategy in place for retirement beyond the traditional 401k?

I work with {industry} folks and there's one approach that's been getting traction.

Up for a quick call?"""
    },
    {
        "id": "opener_email_v3",
        "subject": "worth a call?",
        "body": """Hi {first_name},

Working with some {industry} owners on retirement planning and wanted to see if you'd be open to a brief call.

No pitch, just sharing what's been working. 30 minutes tops.

Interested?"""
    },
    {
        "id": "opener_email_v4",
        "subject": "one thing",
        "body": """{first_name} —

Quick one: are you happy with how your retirement plan is structured?

A lot of {industry} folks I talk to aren't, usually because they didn't know there were other options.

Can I send you a quick overview?"""
    },
    {
        "id": "opener_email_v5",
        "subject": "business owners",
        "body": """Hey {first_name},

I help business owners set up retirement plans that actually make sense. Better tax breaks and more flexibility than a 401k.

If you're curious, happy to walk you through it. 

30 min call work?"""
    },
    {
        "id": "opener_email_v6",
        "subject": "your retirement",
        "body": """{first_name} —

Most {industry} owners I talk to don't realize there's a better way to save for retirement than a standard 401k.

Want to see if it makes sense for you?

No pressure, just a quick 15-minute call.
"""
    },
    {
        "id": "opener_email_v7",
        "subject": "retirement question",
        "body": """Hi {first_name},

Quick question: are you exploring options beyond the standard 401k for retirement?

I work with {industry} owners on tax-advantaged strategies that tend to outperform traditional plans.

Worth a quick 30 min call?"""
    },
    {
        "id": "opener_email_v8",
        "subject": "one question",
        "body": """{first_name} —

Do you have a solid exit/retirement plan in place, or is that still something you're figuring out?

I help {industry} folks structure plans that give more flexibility and better tax treatment.

Open to a quick call this week?"""
    },
    {
        "id": "opener_email_v9",
        "subject": "for {industry} owners",
        "body": """Hey {first_name},

Working with a few {industry} business owners on retirement planning and wanted to reach out.

Most don't realize there are ways to save significantly more than a 401k allows while reducing taxes.

30 min to walk you through it?"""
    },
    {
        "id": "opener_email_v10",
        "subject": "planning ahead",
        "body": """{first_name} —

Most {industry} owners I talk to don't have a real plan for what happens when they slow down or exit.

If you're open, I can show you a strategy that builds wealth faster and gives you more control.

Quick call work for you?"""
    },
    {
        "id": "opener_email_v11",
        "subject": "question about retirement",
        "body": """Hi {first_name},

Are you happy with your current retirement setup, or open to seeing other options?

I specialize in helping {industry} owners structure plans that give better returns + tax benefits.

15 minutes this week?"""
    },
    {
        "id": "opener_email_v12",
        "subject": "curious",
        "body": """{first_name} —

Curious if you've looked into alternatives to standard retirement plans for business owners.

Most {industry} folks I work with didn't know these existed until recently.

Worth a conversation?"""
    }
]

# Follow-up 1 variants - gentle bump, give them an out
FOLLOWUP_1_EMAIL_VARIANTS = [
    {
        "id": "followup1_email_v1",
        "subject": "Re: {previous_subject}",
        "body": """Hey {first_name}, just bumping this.

Should I close the loop, or is it worth a quick call?"""
    },
    {
        "id": "followup1_email_v2",
        "subject": "following up",
        "body": """{first_name} —

Circling back on this.

Still open to a brief call, or should I take you off my list?"""
    },
    {
        "id": "followup1_email_v3",
        "subject": "Re: {previous_subject}",
        "body": """Hi {first_name},

Totally get it if timing isn't right.

But if you're curious, 30 min call this week?"""
    },
    {
        "id": "followup1_email_v4",
        "subject": "quick check",
        "body": """{first_name} —

Not sure if you saw my last note.

Worth a call or no?"""
    },
    {
        "id": "followup1_email_v5",
        "subject": "Re: {previous_subject}",
        "body": """Hey {first_name},

Following up on this, still interested in a quick call about retirement planning?

Let me know either way."""
    },
    {
        "id": "followup1_email_v6",
        "subject": "checking in",
        "body": """{first_name},

Just making sure this didn't get buried.

Still worth connecting on retirement planning?"""
    },
    {
        "id": "followup1_email_v7",
        "subject": "Re: {previous_subject}",
        "body": """Hey {first_name} —

Wanted to circle back on this. If timing's not right, all good.

Otherwise, 30 min call work?"""
    },
    {
        "id": "followup1_email_v8",
        "subject": "one more try",
        "body": """{first_name},

Last bump on this. Open to a quick call or should I assume it's not a fit?"""
    }
]

# Follow-up 2 variants - final message, no pressure
FOLLOWUP_2_EMAIL_VARIANTS = [
    {
        "id": "followup2_email_v1",
        "subject": "last one",
        "body": """All good either way — last message from me.

If you want, grab a time here: {calendly_link}"""
    },
    {
        "id": "followup2_email_v2",
        "subject": "closing the loop",
        "body": """{first_name}, assume timing isn't right. No worries.

If that changes: {calendly_link}"""
    },
    {
        "id": "followup2_email_v3",
        "subject": "Re: {previous_subject}",
        "body": """Hey {first_name} —

Last note from me. If you're interested, here's where you can grab time: {calendly_link}

Otherwise, all good. Thanks."""
    },
    {
        "id": "followup2_email_v4",
        "subject": "final follow up",
        "body": """{first_name},

Won't bug you again after this.

Link if you want to chat: {calendly_link}"""
    },
    {
        "id": "followup2_email_v5",
        "subject": "one more try",
        "body": """Last one, promise.

If you're curious about alternative retirement strategies: {calendly_link}

Otherwise, I'll close the loop."""
    },
    {
        "id": "followup2_email_v6",
        "subject": "last check",
        "body": """{first_name} —

Final note from me. No hard feelings if it's not a fit.

But if you want to explore: {calendly_link}"""
    },
    {
        "id": "followup2_email_v7",
        "subject": "Re: {previous_subject}",
        "body": """Hey {first_name},

Won't take up more of your time after this.

If you're curious: {calendly_link}

Thanks either way."""
    }
]

# Reply engaged variants - when they show interest
REPLY_ENGAGED_EMAIL_VARIANTS = [
    {
        "id": "reply_engaged_v1",
        "subject": "Re: {previous_subject}",
        "body": """Thanks for getting back to me, {first_name}.

Here's a time that works: {calendly_link}

Or let me know what's better for you."""
    },
    {
        "id": "reply_engaged_v2",
        "subject": "Re: {previous_subject}",
        "body": """Perfect — appreciate the reply.

Grab a time here: {calendly_link}

Looking forward to it."""
    },
    {
        "id": "reply_engaged_v3",
        "subject": "Re: {previous_subject}",
        "body": """Great, thanks {first_name}.

When works for you? {calendly_link}"""
    }
]

# SMS opener variants - very short, consent-aware
SMS_OPENER_VARIANTS = [
    {
        "id": "sms_opener_v1",
        "body": "Hey {first_name} — quick one: are you open to a 30 min call this week about retirement planning? Reply YES for times. Reply STOP to opt out."
    },
    {
        "id": "sms_opener_v2",
        "body": "{first_name}, do you have 30 min this week to talk retirement strategy? Reply YES if interested. STOP to unsubscribe."
    },
    {
        "id": "sms_opener_v3",
        "body": "Hi {first_name} — working with {industry} owners on retirement planning. Up for a quick call? Reply YES or STOP."
    },
    {
        "id": "sms_opener_v4",
        "body": "{first_name} — quick question about retirement planning for {industry} owners. 30 min call? Reply YES. Reply STOP to opt out."
    },
    {
        "id": "sms_opener_v5",
        "body": "Hey {first_name}, helping business owners optimize retirement plans. Curious? Reply YES for call. STOP to unsubscribe."
    }
]

# SMS follow-up variants
SMS_FOLLOWUP_VARIANTS = [
    {
        "id": "sms_followup_v1",
        "body": "{first_name}, following up on retirement planning call. Still interested? Reply YES or STOP."
    },
    {
        "id": "sms_followup_v2",
        "body": "Hey {first_name} — checking in. Want that retirement planning call? YES or STOP."
    },
    {
        "id": "sms_followup_v3",
        "body": "{first_name}, last follow up. Interested in call? Reply YES. STOP to opt out."
    }
]

# SMS appointment reminders
SMS_REMINDER_24H_VARIANTS = [
    {
        "id": "sms_reminder_24h_v1",
        "body": "Hey {first_name} — reminder: our call tomorrow at {time}. Looking forward to it!"
    },
    {
        "id": "sms_reminder_24h_v2",
        "body": "{first_name}, quick reminder: we're talking tomorrow at {time}. See you then."
    },
    {
        "id": "sms_reminder_24h_v3",
        "body": "Hi {first_name} — call tomorrow at {time}. If you need to reschedule: {calendly_link}"
    }
]

SMS_REMINDER_2H_VARIANTS = [
    {
        "id": "sms_reminder_2h_v1",
        "body": "Hey {first_name} — we're on in 2 hours at {time}. Meeting link: {meeting_url}"
    },
    {
        "id": "sms_reminder_2h_v2",
        "body": "{first_name}, reminder: call in 2 hours at {time}. Link: {meeting_url}"
    },
    {
        "id": "sms_reminder_2h_v3",
        "body": "Quick reminder {first_name} — call at {time} (2 hours). {meeting_url}"
    }
]

# Confirmation email after booking
APPOINTMENT_CONFIRMED_EMAIL_VARIANTS = [
    {
        "id": "appointment_confirmed_v1",
        "subject": "we're confirmed",
        "body": """Hey {first_name},

You're all set for {date} at {time}.

Meeting link: {meeting_url}

Looking forward to it."""
    },
    {
        "id": "appointment_confirmed_v2",
        "subject": "confirmed - {date} at {time}",
        "body": """Thanks {first_name} —

We're confirmed for {date} at {time}.

Here's your link: {meeting_url}

See you then!"""
    },
    {
        "id": "appointment_confirmed_v3",
        "subject": "all set",
        "body": """Perfect, {first_name}.

{date} at {time}: {meeting_url}

Talk soon."""
    }
]

# No-show recovery
NO_SHOW_EMAIL_VARIANTS = [
    {
        "id": "no_show_v1",
        "subject": "missed you",
        "body": """Hey {first_name} —

We were scheduled for {time} but I didn't see you on the call.

All good if something came up. Want to reschedule? {calendly_link}"""
    },
    {
        "id": "no_show_v2",
        "subject": "Re: our call",
        "body": """{first_name},

Looks like we missed each other at {time}.

If you still want to chat: {calendly_link}"""
    },
    {
        "id": "no_show_v3",
        "subject": "reschedule?",
        "body": """Hey {first_name} — didn't catch you at {time}.

No worries if you got pulled away. Reschedule here: {calendly_link}"""
    }
]


# Master registry of all variants
TEMPLATE_VARIANTS = {
    "opener_email": OPENER_EMAIL_VARIANTS,
    "followup_1_email": FOLLOWUP_1_EMAIL_VARIANTS,
    "followup_2_email": FOLLOWUP_2_EMAIL_VARIANTS,
    "reply_engaged_email": REPLY_ENGAGED_EMAIL_VARIANTS,
    "sms_opener": SMS_OPENER_VARIANTS,
    "sms_followup": SMS_FOLLOWUP_VARIANTS,
    "sms_reminder_24h": SMS_REMINDER_24H_VARIANTS,
    "sms_reminder_2h": SMS_REMINDER_2H_VARIANTS,
    "appointment_confirmed_email": APPOINTMENT_CONFIRMED_EMAIL_VARIANTS,
    "no_show_email": NO_SHOW_EMAIL_VARIANTS
}


def get_variant_count(stage: str) -> int:
    """Get number of variants for a stage"""
    return len(TEMPLATE_VARIANTS.get(stage, []))


def get_all_variant_ids(stage: str) -> list[str]:
    """Get all variant IDs for a stage"""
    variants = TEMPLATE_VARIANTS.get(stage, [])
    return [v["id"] for v in variants]
