
import asyncio
import aiosqlite
from pathlib import Path

async def check_db():
    db_path = Path("d:/SovereignAI/database/sovereign.db")
    if not db_path.exists():
        print(f"DB not found at {db_path}")
        return
    
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT id, name, path FROM models") as cursor:
            rows = await cursor.fetchall()
            print(f"Found {len(rows)} models:")
            for row in rows:
                print(f"ID: {row['id']} | Name: {row['name']} | Path: {row['path']}")

if __name__ == "__main__":
    asyncio.run(check_db())
