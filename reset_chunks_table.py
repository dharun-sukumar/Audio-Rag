import sys
import os

# Add root to python path so app imports work
sys.path.append(os.getcwd())

from app.core.database import engine
from app.models.chunk import Chunk

def reset_chunks():
    print("Dropping chunks table...")
    try:
        Chunk.__table__.drop(engine)
        print("Chunks table dropped.")
    except Exception as e:
        print(f"Error dropping table (might not exist): {e}")

    print("Recreating chunks table...")
    Chunk.__table__.create(engine)
    print("Chunks table recreated with new schema.")

if __name__ == "__main__":
    confirm = input("This will DELETE ALL DATA in the 'chunks' table. Are you sure? (y/n): ")
    if confirm.lower() == 'y':
        reset_chunks()
    else:
        print("Operation cancelled.")
