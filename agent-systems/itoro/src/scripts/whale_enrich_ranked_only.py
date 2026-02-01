"""
Standalone script: enrich ranked_whales.json and whale_history.csv with 7d winrate and avg hold time.
Uses Hyperliquid user_fills (last 7 days). No Apify fetch, no full whale agent run.
Run: python -m src.scripts.whale_enrich_ranked_only
"""

import json
import os
import sys
import time
from pathlib import Path

# Ensure project root on path
_project_root = Path(__file__).resolve().parents[2]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

try:
    from src.config import (
        WHALE_DATA_DIR,
        WHALE_RANKED_FILE,
        WHALE_HISTORY_FILE,
        WHALE_ENRICHMENT_MAX_WALLETS,
        WHALE_ENRICHMENT_RATE_LIMIT_SEC,
    )
except ImportError:
    WHALE_DATA_DIR = os.path.join("src", "data", "whale_dump")
    WHALE_RANKED_FILE = "ranked_whales.json"
    WHALE_HISTORY_FILE = "whale_history.csv"
    WHALE_ENRICHMENT_MAX_WALLETS = 1000
    WHALE_ENRICHMENT_RATE_LIMIT_SEC = 0.5

from src.scripts.trading.hyperliquid_enrichment import enrich_wallet_7d_from_hyperliquid


def main():
    data_dir = Path(WHALE_DATA_DIR)
    ranked_path = data_dir / WHALE_RANKED_FILE
    history_path = data_dir / WHALE_HISTORY_FILE

    if not ranked_path.exists():
        print(f"ranked_whales.json not found at {ranked_path}")
        return 1

    with open(ranked_path, "r", encoding="utf-8") as f:
        ranked = json.load(f)

    addresses = list(ranked.keys())
    if not addresses:
        print("No wallets in ranked_whales.json")
        return 0

    cap = min(len(addresses), WHALE_ENRICHMENT_MAX_WALLETS)
    print(f"Enriching up to {cap} wallets (rate limit {WHALE_ENRICHMENT_RATE_LIMIT_SEC}s)...")

    for i, addr in enumerate(addresses[:cap]):
        try:
            enriched = enrich_wallet_7d_from_hyperliquid(addr)
            ranked[addr]["winrate_7d"] = enriched["winrate_7d"]
            ranked[addr]["avg_holding_period_7d"] = enriched["avg_holding_period_7d"]
            print(f"  [{i+1}/{cap}] {addr[:10]}... winrate_7d={enriched['winrate_7d']:.3f} avg_hold_7d={enriched['avg_holding_period_7d']:.0f}s")
        except Exception as e:
            print(f"  [{i+1}/{cap}] {addr[:10]}... skip: {e}")
        if i < cap - 1:
            time.sleep(WHALE_ENRICHMENT_RATE_LIMIT_SEC)

    with open(ranked_path, "w", encoding="utf-8") as f:
        json.dump(ranked, f, indent=2)
    print(f"Wrote {ranked_path}")

    if history_path.exists():
        import pandas as pd
        df = pd.read_csv(history_path)
        for col in ("winrate_7d", "avg_holding_period_7d"):
            if col not in df.columns:
                df[col] = 0.5 if col == "winrate_7d" else 86400.0
        addr_col = "address" if "address" in df.columns else df.columns[0]
        for idx, row in df.iterrows():
            a = row.get(addr_col)
            if a and a in ranked:
                df.at[idx, "winrate_7d"] = ranked[a].get("winrate_7d", 0.5)
                df.at[idx, "avg_holding_period_7d"] = ranked[a].get("avg_holding_period_7d", 86400.0)
        df.to_csv(history_path, index=False)
        print(f"Backfilled whale_history.csv at {history_path}")
    else:
        print(f"whale_history.csv not found at {history_path} (skipped)")

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
