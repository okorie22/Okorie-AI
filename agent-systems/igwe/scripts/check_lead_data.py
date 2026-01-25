"""Check recent leads for job_title and city data"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "iul_appointment_setter.db"

conn = sqlite3.connect(str(DB_PATH))
cursor = conn.cursor()

cursor.execute("""
    SELECT first_name, last_name, email, job_title, city, state, employee_size, company_name
    FROM leads 
    ORDER BY id DESC 
    LIMIT 15
""")

results = cursor.fetchall()

print("\nRecent leads with job_title and city:")
print("=" * 150)
for row in results:
    fname, lname, email, job_title, city, state, emp_size, company = row
    job_title = job_title or "(no title)"
    city = city or "(no city)"
    emp_size = emp_size or 0
    print(f"{fname} {lname:20s} | {job_title:30s} | {city:20s}, {state:10s} | emp_size={emp_size:3d} | {company}")

conn.close()
