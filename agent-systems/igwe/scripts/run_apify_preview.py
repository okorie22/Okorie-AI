"""
Manual Apify preview runner.

Purpose:
- Run the configured Apify actor(s) on-demand (ignores warmup/weekend gating).
- Show parameter rotation (params + hash per run).
- Apply the exact CSV mapping + US-only filter used by the system.
- Import new leads (dedupe by email/phone) and start conversations (state NEW).

This is meant for *testing lead quality* while SendGrid/Twilio are in test mode.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
from pathlib import Path
import sys

from loguru import logger

# Ensure `src/` package is importable when run from scripts/
PROJECT_ROOT = Path(__file__).resolve().parents[1]  # .../igwe
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.storage.database import SessionLocal
from src.storage.models import Lead, LeadSourceRun
from src.storage.repositories import LeadRepository
from src.workflow.state_machine import WorkflowEngine
from src.sources.apify import ApifyClient
from src.sources.param_rotator import ParamRotator
from src.ingestion.apify_adapter import ApifyLeadAdapter
from src.intelligence.scorer import LeadScorer
from src.config import apify_config


def _pick_actor_id() -> str:
    actors = apify_config.actors
    if not actors:
        raise RuntimeError("No Apify actors configured. Set APIFY_ACTOR_1.. in .env")

    for a in actors:
        if "pipelinelabs" in a:
            return a
    return actors[0]


def _print_lead_sample(leads_data: list[dict], max_rows: int) -> None:
    print("\nSample leads (post-mapping + US filter):")
    print("-" * 80)
    for i, ld in enumerate(leads_data[:max_rows], start=1):
        md = ld.get("metadata") or {}
        print(
            f"{i:02d}. {ld.get('first_name','')} {ld.get('last_name','')}"
            f" | {ld.get('email','')}"
            f" | {ld.get('company_name','')}"
            f" | {ld.get('state','')}"
            f" | country={md.get('country','')}"
        )
    print("-" * 80)


async def _run_once(apify_client: ApifyClient, actor_id: str, params: dict, output_path: Path) -> dict:
    return await apify_client.run_and_download(actor_id, params, output_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Apify preview/import on-demand")
    parser.add_argument("--runs", type=int, default=2, help="Number of actor runs to execute (default: 2)")
    parser.add_argument("--sample", type=int, default=10, help="How many mapped leads to print (default: 10)")
    parser.add_argument("--import", dest="do_import", action="store_true", help="Import into DB + start conversations")
    parser.add_argument("--no-import", dest="do_import", action="store_false", help="Preview only (no DB writes)")
    parser.set_defaults(do_import=True)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        actor_id = _pick_actor_id()
        apify_client = ApifyClient()
        rotator = ParamRotator(db)
        adapter = ApifyLeadAdapter()
        scorer = LeadScorer(db)
        lead_repo = LeadRepository(db)
        engine = WorkflowEngine(db)

        used_hashes = rotator.get_used_param_hashes(actor_id, limit=100)
        print(f"Actor: {actor_id}")
        print(f"Seed used param hashes in DB: {len(used_hashes)}")
        print(f"DB import enabled: {args.do_import}")

        total_rows = 0
        total_mapped = 0
        total_imported = 0
        total_duplicates = 0
        total_conversations = 0

        for run_num in range(1, args.runs + 1):
            params = rotator.get_next_params(actor_id, used_hashes)
            params_hash = rotator.generate_param_hash(params)
            used_hashes.append(params_hash)  # advance rotation in this run

            print("\n" + "=" * 80)
            print(f"RUN {run_num}/{args.runs} @ {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
            print(f"params_hash: {params_hash}")
            print(f"params: {params}")

            output_path = Path(f"/tmp/apify_preview_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_run{run_num}.csv")

            # Execute Apify run (sync wrapper around async)
            result = asyncio.run(_run_once(apify_client, actor_id, params, output_path))
            csv_path = Path(result["csv_path"])

            # Record run in DB for observability (safe, no messaging involved)
            run_record = LeadSourceRun(
                run_id=result["run_id"],
                actor_name=actor_id,
                params_hash=params_hash,
                params_json=params,
                dataset_id=result.get("dataset_id"),
                status="completed",
                token_alias="rotating",
                started_at=datetime.utcnow(),
                finished_at=datetime.utcnow(),
            )
            db.add(run_record)
            db.commit()

            # Map CSV -> leads (includes required-field checks + US-only filter + optional CSV dedupe)
            leads_data = adapter.process_csv(csv_path, actor_id, deduplicate=True)
            total_mapped += len(leads_data)

            # Best-effort row count: DictReader length pre-filter isn't retained; show mapped count instead.
            print(f"Mapped leads (after US-only + required fields + CSV-dedupe): {len(leads_data)}")
            _print_lead_sample(leads_data, args.sample)

            imported_this_run = 0
            duplicates_this_run = 0
            conversations_this_run = 0

            if args.do_import:
                new_leads: list[Lead] = []
                for ld in leads_data:
                    existing = lead_repo.find_by_email(ld["email"])
                    if not existing and ld.get("phone"):
                        existing = lead_repo.find_by_phone(ld["phone"])
                    if existing:
                        duplicates_this_run += 1
                        continue

                    lead = Lead(**{k: v for k, v in ld.items() if k != "metadata"})
                    db.add(lead)
                    new_leads.append(lead)

                db.commit()

                for lead in new_leads:
                    try:
                        scorer.score_lead(lead)
                    except Exception as e:
                        logger.error(f"Error scoring lead {lead.id}: {e}")
                db.commit()

                for lead in new_leads:
                    if lead.email:
                        conv = engine.start_conversation(lead)
                        conversations_this_run += 1
                        # Print a tiny proof for first few
                        if conversations_this_run <= 5:
                            print(f"Conversation created: id={conv.id}, state={conv.state.value}, channel={conv.channel.value}")

                imported_this_run = len(new_leads)

                # Update run stats
                run_record.total_rows = len(leads_data)
                run_record.new_leads_imported = imported_this_run
                run_record.duplicates_skipped = duplicates_this_run
                db.commit()

            total_imported += imported_this_run
            total_duplicates += duplicates_this_run
            total_conversations += conversations_this_run

            # cleanup CSV
            try:
                if csv_path.exists():
                    csv_path.unlink()
            except Exception:
                pass

            print(f"Imported new leads: {imported_this_run} | DB duplicates skipped: {duplicates_this_run} | Conversations started: {conversations_this_run}")

        print("\n" + "=" * 80)
        print("SUMMARY")
        print(f"Runs: {args.runs}")
        print(f"Mapped leads total: {total_mapped}")
        print(f"Imported new leads total: {total_imported}")
        print(f"Duplicates skipped total: {total_duplicates}")
        print(f"Conversations started total: {total_conversations}")
        print("=" * 80)

        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())

