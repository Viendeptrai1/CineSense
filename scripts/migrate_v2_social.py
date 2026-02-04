import sys
import os

# Add parent directory to path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from etl_pipeline.db_postgres import get_engine, init_database

def migrate():
    engine = get_engine()
    
    print("🚀 Starting Database Migration (Social V2)...")
    
    # 1. Create new tables (Users, Interactions) first
    # This ensures 'users' table exists for the Foreign Key constraint
    print("🔨 Creating new tables (Users, Watchlist, ReviewLikes)...")
    init_database()

    # 2. Alter 'reviews' table to add new columns
    with engine.connect() as conn:
        print("🔧 Altering 'reviews' table...")
        conn.execute(text("""
            ALTER TABLE reviews 
            ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS likes_count INTEGER DEFAULT 0;
        """))
        conn.commit()
        print("✅ 'reviews' table updated.")
    
    print("✅ Migration complete!")

if __name__ == "__main__":
    migrate()
