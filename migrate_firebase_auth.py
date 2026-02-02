"""
Migration script to rename google_sub to firebase_uid in users table

This migration updates the column name to reflect the proper use of Firebase Auth
instead of Google OAuth.
"""

from app.core.database import engine
from sqlalchemy import text

def migrate():
    """Rename google_sub column to firebase_uid"""
    
    with engine.connect() as conn:
        # Check if old column exists
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='users' 
            AND column_name='google_sub'
        """))
        
        if not result.fetchone():
            print("✓ Column 'google_sub' does not exist. Migration may have already run.")
            
            # Check if new column exists
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='users' 
                AND column_name='firebase_uid'
            """))
            
            if result.fetchone():
                print("✓ Column 'firebase_uid' already exists. No migration needed.")
            else:
                print("⚠ Neither google_sub nor firebase_uid exists. Creating firebase_uid...")
                conn.execute(text("""
                    ALTER TABLE users 
                    ADD COLUMN firebase_uid VARCHAR UNIQUE NOT NULL
                """))
                conn.commit()
                print("✓ Added firebase_uid column")
            
            return
        
        # Rename the column
        print("Renaming 'google_sub' to 'firebase_uid' in users table...")
        conn.execute(text("""
            ALTER TABLE users 
            RENAME COLUMN google_sub TO firebase_uid
        """))
        conn.commit()
        
        print("✓ Migration completed successfully!")
        print("  - Renamed 'google_sub' to 'firebase_uid'")
        print("  - Existing user data preserved")
        print("  - Index and constraints maintained")

if __name__ == "__main__":
    try:
        migrate()
    except Exception as e:
        print(f"✗ Migration failed: {str(e)}")
        raise
