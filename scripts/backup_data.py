#!/usr/bin/env python3
import os
import subprocess
import time
from datetime import datetime
import httpx
from loguru import logger

# Configuration
POSTGRES_CONTAINER = "cinesense-postgres"
QDRANT_CONTAINER = "cinesense-qdrant"
QDRANT_URL = "http://localhost:6333"
SEED_DIR = "infra/seed"
POSTGRES_SEED = os.path.join(SEED_DIR, "postgres/init_data.sql")
QDRANT_SEED_DIR = os.path.join(SEED_DIR, "qdrant")

def backup_postgres():
    logger.info("🐘 Backing up PostgreSQL...")
    try:
        # Get env vars or defaults
        db_user = os.getenv("POSTGRES_USER", "cinesense")
        db_name = os.getenv("POSTGRES_DB", "cinesense_db")
        
        # Run pg_dump inside container
        cmd = [
            "docker", "exec", POSTGRES_CONTAINER,
            "pg_dump", "-U", db_user, "-d", db_name, "--clean", "--if-exists"
        ]
        
        with open(POSTGRES_SEED, "w") as f:
            subprocess.run(cmd, stdout=f, check=True)
            
        logger.success(f"PostgreSQL dump saved to {POSTGRES_SEED}")
    except Exception as e:
        logger.error(f"Failed to backup PostgreSQL: {e}")

def backup_qdrant():
    logger.info("🛰️  Backing up Qdrant snapshots...")
    try:
        # 1. Create snapshot for the 'movie_reviews' collection
        collection_name = "movie_reviews"
        # We need to install httpx if not already there, but we assume it's in venv
        with httpx.Client() as client:
            resp = client.post(f"{QDRANT_URL}/collections/{collection_name}/snapshots")
            resp.raise_for_status()
            snapshot_info = resp.json()["result"]
            snapshot_name = snapshot_info["name"]
            
        logger.info(f"Created snapshot: {snapshot_name}")
        
        # 2. Extract snapshot from container to infra/seed/qdrant
        # Qdrant snapshots are stored at /qdrant/snapshots/movie_reviews/
        container_path = f"/qdrant/snapshots/{collection_name}/{snapshot_name}"
        local_path = os.path.join(QDRANT_SEED_DIR, "movie_reviews_snapshot.snapshot")
        
        subprocess.run(["docker", "cp", f"{QDRANT_CONTAINER}:{container_path}", local_path], check=True)
        
        logger.success(f"Qdrant snapshot saved to {local_path}")
    except Exception as e:
        logger.error(f"Failed to backup Qdrant: {e}")

def main():
    os.makedirs(os.path.dirname(POSTGRES_SEED), exist_ok=True)
    os.makedirs(QDRANT_SEED_DIR, exist_ok=True)
    
    backup_postgres()
    backup_qdrant()
    
    logger.success("✨ Backup process completed!")

if __name__ == "__main__":
    main()
