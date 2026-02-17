from sqlalchemy import text
from app.core.database import engine

def purge_memory_tables():
    print("Purging memory tables to enforce Strict Intake...")
    with engine.connect() as conn:
        try:
            conn.execute(text("TRUNCATE TABLE semantic_memories CASCADE;"))
            conn.execute(text("TRUNCATE TABLE entity_memories CASCADE;"))
            conn.execute(text("TRUNCATE TABLE chunks CASCADE;")) 
            # We also clear chunks because they were generated from loose intake.
            # We want a clean slate.
            conn.commit()
            print("Memory tables purged successfully.")
        except Exception as e:
            print(f"Error purging tables: {e}")
            conn.rollback()

if __name__ == "__main__":
    purge_memory_tables()
