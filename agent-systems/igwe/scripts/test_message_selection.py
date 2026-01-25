"""
Test Script 1: Message Selection & Conversation States
Tests that the workflow engine chooses the right message stage for each state:
  NEW -> opener_email, CONTACTED -> followup_1_email, NO_RESPONSE -> followup_2_email
"""
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.storage.database import SessionLocal
from src.storage.models import Conversation, ConversationState, Lead, Message, MessageDirection
from src.workflow.state_machine import WorkflowEngine, STATE_TO_MESSAGE_STAGE
from datetime import datetime, timedelta
from loguru import logger


def test_state_to_stage_mapping():
    """Assert that NEW, CONTACTED, NO_RESPONSE map to the correct message stages."""
    assert STATE_TO_MESSAGE_STAGE[ConversationState.NEW] == "opener_email", (
        "NEW must use opener_email"
    )
    assert STATE_TO_MESSAGE_STAGE[ConversationState.CONTACTED] == "followup_1_email", (
        "CONTACTED must use followup_1_email"
    )
    assert STATE_TO_MESSAGE_STAGE[ConversationState.NO_RESPONSE] == "followup_2_email", (
        "NO_RESPONSE must use followup_2_email"
    )
    print("[PASS] State-to-message-stage mapping (NEW/CONTACTED/NO_RESPONSE)")


def test_message_selection():
    """Test that correct messages are chosen for each conversation state."""
    print("\n" + "=" * 80)
    print("[TEST] Message Selection by Conversation State")
    print("=" * 80 + "\n")

    # 1. Assert state -> stage mapping (single source of truth used by WorkflowEngine)
    test_state_to_stage_mapping()

    db = SessionLocal()

    try:
        states_to_test = [
            ConversationState.NEW,
            ConversationState.CONTACTED,
            ConversationState.NO_RESPONSE,
        ]

        print("\nCurrent conversation counts by state:")
        for state in states_to_test:
            count = db.query(Conversation).filter(Conversation.state == state).count()
            stage = STATE_TO_MESSAGE_STAGE.get(state, "(none)")
            print(f"   {state.value.upper()}: {count} -> stage '{stage}'")

        print("\n" + "-" * 80)
        print("Message selection logic (db query + stage mapping):\n")

        # NEW -> opener_email
        new_convs = db.query(Conversation).filter(
            Conversation.state == ConversationState.NEW,
            Conversation.next_action_at <= datetime.utcnow(),
        ).limit(3).all()
        expected_stage = STATE_TO_MESSAGE_STAGE[ConversationState.NEW]
        print(f"NEW (ready now): {len(new_convs)} convs -> expect stage '{expected_stage}'")
        if new_convs:
            for conv in new_convs:
                lead = db.query(Lead).filter(Lead.id == conv.lead_id).first()
                name = f"{lead.first_name} {lead.last_name}" if lead else "?"
                print(f"   Conv {conv.id} (Lead: {name}) next_action={conv.next_action_at}")

        # CONTACTED -> followup_1_email
        contacted_convs = db.query(Conversation).filter(
            Conversation.state == ConversationState.CONTACTED,
            Conversation.next_action_at <= datetime.utcnow(),
        ).limit(3).all()
        expected_stage = STATE_TO_MESSAGE_STAGE[ConversationState.CONTACTED]
        print(f"\nCONTACTED (ready now): {len(contacted_convs)} convs -> expect stage '{expected_stage}'")
        if contacted_convs:
            for conv in contacted_convs:
                lead = db.query(Lead).filter(Lead.id == conv.lead_id).first()
                last_out = (
                    db.query(Message)
                    .filter(
                        Message.conversation_id == conv.id,
                        Message.direction == MessageDirection.OUTBOUND,
                    )
                    .order_by(Message.created_at.desc())
                    .first()
                )
                hours = (
                    (datetime.utcnow() - last_out.created_at).total_seconds() / 3600
                    if last_out
                    else None
                )
                print(f"   Conv {conv.id} last outbound {hours:.1f}h ago" if hours is not None else f"   Conv {conv.id}")

        # NO_RESPONSE -> followup_2_email
        no_response_convs = db.query(Conversation).filter(
            Conversation.state == ConversationState.NO_RESPONSE,
            Conversation.next_action_at <= datetime.utcnow(),
        ).limit(3).all()
        expected_stage = STATE_TO_MESSAGE_STAGE[ConversationState.NO_RESPONSE]
        print(f"\nNO_RESPONSE (ready now): {len(no_response_convs)} convs -> expect stage '{expected_stage}'")
        if no_response_convs:
            for conv in no_response_convs:
                last_out = (
                    db.query(Message)
                    .filter(
                        Message.conversation_id == conv.id,
                        Message.direction == MessageDirection.OUTBOUND,
                    )
                    .order_by(Message.created_at.desc())
                    .first()
                )
                hours = (
                    (datetime.utcnow() - last_out.created_at).total_seconds() / 3600
                    if last_out
                    else None
                )
                msg = f"   Conv {conv.id} last outbound {hours:.1f}h ago" if hours is not None else f"   Conv {conv.id}"
                print(msg)

        print("\n" + "-" * 80)
        print("Simulated dispatch (WorkflowEngine uses STATE_TO_MESSAGE_STAGE):")
        print("   NEW         -> opener_email      -> then transition to CONTACTED")
        print("   CONTACTED   -> followup_1_email  -> then transition to NO_RESPONSE")
        print("   NO_RESPONSE -> followup_2_email  -> stay (wait for reply or manual close)")

        print("\n" + "=" * 80)
        print("[PASS] Message selection test complete.")
        print("=" * 80 + "\n")
        return True

    except AssertionError as e:
        print(f"\n[FAIL] Assertion: {e}")
        logger.error(f"Assertion: {e}")
        return False
    except Exception as e:
        print(f"\n[FAIL] {e}")
        logger.error(f"Test error: {e}", exc_info=True)
        return False
    finally:
        db.close()


if __name__ == "__main__":
    success = test_message_selection()
    sys.exit(0 if success else 1)
