"""
📢 Telegram Management Agent
Automates Telegram channel programming with AI-generated content, templates,
and data-driven updates for marketing, education, and community engagement.
"""

from __future__ import annotations

import logging
import random
import threading
import time
from datetime import datetime
from typing import List, Optional

import requests
import schedule

try:
    from ..shared.config import (
        TELEGRAM_BOT_TOKEN,
        TELEGRAM_CHANNEL_ID,
        TELEGRAM_CONTENT_ENABLED,
        TELEGRAM_CONTENT_SCHEDULES,
        TELEGRAM_CONTENT_TOPICS,
        TELEGRAM_CONTENT_ROTATION,
        TELEGRAM_CONTENT_MAX_RETRIES,
        GMGN_PROMO_LINK,
        FOREX_COMMUNITY_LINK,
        DEEPSEEK_API_KEY,
    )
    from ..shared.utils import TelegramNotifier
except ImportError:  # pragma: no cover - support running as script
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from shared.config import (  # type: ignore
        TELEGRAM_BOT_TOKEN,
        TELEGRAM_CHANNEL_ID,
        TELEGRAM_CONTENT_ENABLED,
        TELEGRAM_CONTENT_SCHEDULES,
        TELEGRAM_CONTENT_TOPICS,
        TELEGRAM_CONTENT_ROTATION,
        TELEGRAM_CONTENT_MAX_RETRIES,
        GMGN_PROMO_LINK,
        FOREX_COMMUNITY_LINK,
        DEEPSEEK_API_KEY,
    )
    from shared.utils import TelegramNotifier  # type: ignore


logger = logging.getLogger(__name__)


# =============================================================================
# 🎨 CONTENT GENERATION HELPERS
# =============================================================================

class ContentGenerator:
    """LLM-backed content generator with DeepSeek integration."""

    CHAT_ENDPOINT = "https://api.deepseek.com/v1/chat/completions"

    def __init__(self, api_key: Optional[str]) -> None:
        self.api_key = api_key
        self.http = requests.Session() if api_key else None

    def generate_market_analysis(self, symbol: str, topics: List[str]) -> Optional[str]:
        prompt_topics = ", ".join(topics[:3]) if topics else "technical levels, catalysts, risk management"
        prompt = (
            "Write a concise market update for Telegram subscribers.\n"
            f"Focus on {symbol} highlighting {prompt_topics}. Provide clear actionable insight, "
            "risk guidance, and end with an engaging question."
        )
        return self._call_deepseek(prompt)

    def generate_trading_tip(self) -> Optional[str]:
        prompt = (
            "Provide one practical forex trading tip in 120 words or less. "
            "Format with a title, key insight, and quick action steps."
        )
        return self._call_deepseek(prompt)

    def generate_engagement_post(self) -> Optional[str]:
        prompt = (
            "Create a Telegram post that encourages community engagement about trading psychology. "
            "Include a relatable scenario and end with a question inviting replies."
        )
        return self._call_deepseek(prompt)

    def _call_deepseek(self, prompt: str) -> Optional[str]:
        if not self.api_key or not self.http:
            return None

        payload = {
            "model": "deepseek-chat",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a professional trading coach crafting concise, high-value Telegram posts "
                        "for a premium trading community. Use friendly, motivational tone."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.6,
            "max_tokens": 400,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = self.http.post(self.CHAT_ENDPOINT, json=payload, headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()
            choices = data.get("choices") or []
            if choices:
                text = choices[0].get("message", {}).get("content", "")
                return text.strip() if text else None
        except requests.RequestException:
            logger.exception("DeepSeek content generation failed")
        return None


class TemplateContent:
    """Fallback templates when AI generation is unavailable."""

    MARKET_TEMPLATE = """
📊 {symbol} Market Pulse

Support: {support}
Resistance: {resistance}
Momentum: {momentum}

📌 Insight: {insight}

How are you positioning around {symbol} this week?
    """.strip()

    TIP_TEMPLATE = """
🧠 Trading Tip Tuesday

🎯 Focus: {topic}
💡 Insight: {insight}
✅ Action: {action}

Drop your experience with this below 👇
    """.strip()

    PROMO_TEMPLATE = """
🐋 Copy My Crypto Trades in Real-Time

Mirror every trade I take on-chain with automated execution.

🔗 Follow my GMGN profile: {gmgn_link}
⚡ Paper trading available while you learn
🤝 Join the winners' circle today!
    """.strip()

    COMMUNITY_TEMPLATE = """
🤝 Community Check-In

What's the biggest challenge you're facing in the markets this week?
Share it below — let's solve it together as a squad 💬
    """.strip()

    def market_analysis(self, symbol: str) -> str:
        support = random.choice(["1.0800", "35,200", "0.382 fib"])
        resistance = random.choice(["1.0950", "36,450", "previous swing high"])
        momentum = random.choice(["Bullish momentum emerging", "Range-bound", "Momentum cooling"])
        insight = random.choice([
            "Wait for a pullback before joining trend moves.",
            "Risk events ahead — scale position size accordingly.",
            "Liquidity is thin; prioritize clean setups only.",
        ])
        return self.MARKET_TEMPLATE.format(
            symbol=symbol,
            support=support,
            resistance=resistance,
            momentum=momentum,
            insight=insight,
        )

    def trading_tip(self) -> str:
        topic = random.choice(["Risk Management", "Trade Journaling", "Scaling In", "News Trading Discipline"])
        insight = random.choice([
            "Define risk before you click — every single trade.",
            "Track emotions alongside numbers to spot hidden patterns.",
            "Break large entries into smaller tranches for better fills.",
        ])
        action = random.choice([
            "Set a max daily loss and step away once hit.",
            "Write a two-sentence recap after each session.",
            "Practice scaling in demo until execution feels natural.",
        ])
        return self.TIP_TEMPLATE.format(topic=topic, insight=insight, action=action)

    def promotional(self, gmgn_link: Optional[str]) -> str:
        link = gmgn_link or "https://gmgn.ai/"
        return self.PROMO_TEMPLATE.format(gmgn_link=link)

    def community_prompt(self) -> str:
        return self.COMMUNITY_TEMPLATE


class DataContent:
    """Lightweight data-driven snippets (placeholder implementation)."""

    def market_snapshot(self) -> str:
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        headline = random.choice([
            "Dollar strength nudges majors ahead of FED minutes.",
            "Bitcoin consolidates while altcoins rotate higher.",
            "Risk appetite returns as equities rebound internationally.",
        ])
        return f"🕒 {now}\n🗞 {headline}"


# =============================================================================
# 🤖 TELEGRAM MANAGEMENT AGENT
# =============================================================================

class TelegramManagementAgent:
    """Automates Telegram content strategy for the commerce ecosystem."""

    def __init__(self) -> None:
        self.telegram = self._init_telegram()
        self.enabled = TELEGRAM_CONTENT_ENABLED and self.telegram is not None
        self.generator = ContentGenerator(DEEPSEEK_API_KEY)
        self.templates = TemplateContent()
        self.data_content = DataContent()

        self.schedules = TELEGRAM_CONTENT_SCHEDULES or ["09:00", "14:00", "19:00"]
        self.rotation = TELEGRAM_CONTENT_ROTATION or ["market", "tip", "promo", "community"]
        self.topics = TELEGRAM_CONTENT_TOPICS or ["momentum", "risk management", "liquidity pockets"]
        self.max_retries = TELEGRAM_CONTENT_MAX_RETRIES or 2

        self.scheduler = schedule.Scheduler()
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._rotation_index = 0

        self._configure_schedule()
        logger.info("Telegram Management Agent initialized (enabled=%s)", self.enabled)

    # --------------------------------------------------------------------- util
    def _init_telegram(self) -> Optional[TelegramNotifier]:
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID:
            return TelegramNotifier(TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID)
        logger.warning("Telegram credentials missing; management agent disabled.")
        return None

    def _configure_schedule(self) -> None:
        if not self.enabled:
            return

        for time_str in self.schedules:
            try:
                self.scheduler.every().day.at(time_str).do(self._dispatch_scheduled_post)
                logger.debug("Scheduled Telegram post at %s", time_str)
            except schedule.ScheduleValueError:
                logger.warning("Ignoring invalid schedule time string '%s'", time_str)

    # ------------------------------------------------------------------ control
    def start(self) -> None:
        if not self.enabled:
            logger.info("Telegram Management Agent is disabled; start() is a no-op.")
            return
        if self.running:
            logger.info("Telegram Management Agent already running.")
            return

        self.running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("Telegram Management Agent started.")

    def stop(self) -> None:
        self.running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        logger.info("Telegram Management Agent stopped.")

    def _run_loop(self) -> None:
        while self.running:
            try:
                self.scheduler.run_pending()
            except Exception:
                logger.exception("Error while running scheduled Telegram job")
            time.sleep(1)

    # ----------------------------------------------------------------- posting
    def _dispatch_scheduled_post(self) -> None:
        content_type = self.rotation[self._rotation_index % len(self.rotation)]
        self._rotation_index += 1

        logger.debug("Dispatching scheduled Telegram content type '%s'", content_type)
        if content_type == "market":
            self.post_market_update()
        elif content_type == "tip":
            self.post_trading_tip()
        elif content_type == "promo":
            self.post_promotion()
        else:
            self.post_community_prompt()

    def post_market_update(self, symbol: str = "EUR/USD") -> bool:
        message = self.generator.generate_market_analysis(symbol, self.topics)
        if not message:
            message = self.templates.market_analysis(symbol)
        message += "\n\n" + self.data_content.market_snapshot()
        return self._send_message(message)

    def post_trading_tip(self) -> bool:
        message = self.generator.generate_trading_tip()
        if not message:
            message = self.templates.trading_tip()
        return self._send_message(message)

    def post_promotion(self) -> bool:
        message = self.templates.promotional(GMGN_PROMO_LINK)
        if FOREX_COMMUNITY_LINK:
            message += f"\n\n📣 Forex Signals: {FOREX_COMMUNITY_LINK}"
        return self._send_message(message)

    def post_community_prompt(self) -> bool:
        message = self.generator.generate_engagement_post()
        if not message:
            message = self.templates.community_prompt()
        return self._send_message(message)

    def post_custom(self, message: str) -> bool:
        """Send a custom message immediately."""
        return self._send_message(message)

    # ------------------------------------------------------------------- health
    def health_check(self) -> dict:
        return {
            "agent": "TelegramManagementAgent",
            "running": self.running,
            "enabled": self.enabled,
            "scheduled_posts": len(self.scheduler.jobs),
            "rotation": self.rotation,
            "telegram_configured": self.telegram is not None,
        }

    # ------------------------------------------------------------------ helpers
    def _send_message(self, message: str) -> bool:
        if not self.telegram:
            logger.warning("Cannot send Telegram message: notifier not configured.")
            return False

        attempts = 0
        while attempts <= self.max_retries:
            success = self.telegram.send_message(message)
            if success:
                logger.info("Telegram content dispatched successfully.")
                return True
            attempts += 1
            logger.warning("Retrying Telegram send (attempt %s)", attempts)
            time.sleep(min(5 * attempts, 30))

        logger.error("Failed to dispatch Telegram content after %s attempts.", attempts)
        return False


# =============================================================================
# 🏭 FACTORY + BACKWARD COMPATIBILITY
# =============================================================================

_telegram_management_agent: Optional[TelegramManagementAgent] = None


def get_telegram_management_agent() -> TelegramManagementAgent:
    global _telegram_management_agent
    if _telegram_management_agent is None:
        _telegram_management_agent = TelegramManagementAgent()
    return _telegram_management_agent


def get_signal_service_agent() -> TelegramManagementAgent:
    """
    Backward compatibility shim. Returns the Telegram management agent.
    """
    logger.warning(
        "get_signal_service_agent() is deprecated. "
        "Use get_telegram_management_agent() instead."
    )
    return get_telegram_management_agent()


# =============================================================================
# 🧪 TEST HARNESS
# =============================================================================

def test_telegram_management_agent() -> None:
    """Quick manual test that posts synthetic content."""
    agent = get_telegram_management_agent()
    print("Health:", agent.health_check())
    agent.post_market_update("GBP/USD")
    agent.post_trading_tip()
    agent.post_promotion()
    agent.post_community_prompt()


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    test_telegram_management_agent()

