
import aiosqlite
import asyncio

DB_NAME = "trade_bot.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        # Users whitelist
        await db.execute("""
            CREATE TABLE IF NOT EXISTS allowed_users (
                user_id INTEGER PRIMARY KEY,
                username TEXT
            )
        """)
        
        # Positions history
        await db.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                side TEXT,
                entry_price REAL,
                size_usd REAL,
                pnl REAL,
                status TEXT, -- OPEN, CLOSED, CANCELLED
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await db.commit()
    print(f"Database {DB_NAME} initialized.")

if __name__ == "__main__":
    asyncio.run(init_db())
