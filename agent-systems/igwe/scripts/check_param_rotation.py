"""Check parameter rotation history"""
import sqlite3
import json
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "iul_appointment_setter.db"

conn = sqlite3.connect(str(DB_PATH))
cursor = conn.cursor()

cursor.execute("""
    SELECT params_json, started_at, new_leads_imported
    FROM lead_source_runs 
    ORDER BY started_at DESC 
    LIMIT 5
""")

results = cursor.fetchall()

print("\nLast 5 Apify runs and parameter combinations:")
print("=" * 100)
for i, row in enumerate(results, 1):
    params_json, started_at, new_leads = row
    params = json.loads(params_json)
    
    industry = params.get("companyIndustryIncludes", ["?"])[0]
    state = params.get("personLocationStateIncludes", ["?"])[0]
    emp_size = params.get("companyEmployeeSizeIncludes", ["?"])[0]
    
    print(f"\n{i}. Run at: {started_at}")
    print(f"   Industry: {industry}")
    print(f"   State: {state}")
    print(f"   Employee Size: {emp_size}")
    print(f"   New Leads: {new_leads}")

conn.close()
