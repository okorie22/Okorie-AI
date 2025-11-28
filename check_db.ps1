# PowerShell script to check SQLite database
Write-Host "🔍 Checking SQLite Database Tables..." -ForegroundColor Cyan

$dbPath = "multi-agents/itoro/ai_crypto_agents/data/paper_trading.db"

if (Test-Path $dbPath) {
    Write-Host "✅ Database file exists: $dbPath" -ForegroundColor Green

    # Use Python to check tables
    $pythonScript = @"
import sqlite3
conn = sqlite3.connect('$dbPath')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print(f"Found {len(tables)} tables:")
for table in tables:
    print(f"  - {table[0]}")
conn.close()
"@

    Write-Host "📋 Tables in database:" -ForegroundColor Yellow
    python -c $pythonScript
} else {
    Write-Host "❌ Database file not found: $dbPath" -ForegroundColor Red
}

Write-Host "🎯 Database check complete!" -ForegroundColor Green
