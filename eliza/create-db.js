// Create empty SQLite database for ITORO bridge
import Database from 'better-sqlite3';

const dbPath = 'multi-agents/itoro/ai_crypto_agents/data/paper_trading.db';
console.log(`Creating SQLite database at: ${dbPath}`);

try {
  const db = new Database(dbPath);

  // Create basic tables that the bridge plugin might expect
  db.exec(`
    CREATE TABLE IF NOT EXISTS trades (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      symbol TEXT,
      side TEXT,
      quantity REAL,
      price REAL,
      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS portfolio (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      symbol TEXT,
      quantity REAL,
      avg_price REAL,
      current_price REAL,
      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    );
  `);

  console.log('✓ Database created successfully');
  db.close();
} catch (error) {
  console.error('✗ Failed to create database:', error.message);
  process.exit(1);
}
