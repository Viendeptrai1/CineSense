#!/usr/bin/env python3
import os
import time
import httpx
from loguru import logger

QDRANT_URL = "http://localhost:6333"
SNAPSHOT_PATH = "infra/seed/qdrant/movie_reviews_snapshot.snapshot"
COLLECTION_NAME = "movie_reviews"

def wait_for_qdrant():
    logger.info("⏳ Waiting for Qdrant to be ready...")
    for _ in range(30):
        try:
            resp = httpx.get(f"{QDRANT_URL}/healthz")
            if resp.status_code == 200:
                logger.success("✅ Qdrant is up!")
                return True
        except:
            pass
        time.sleep(1)
    return False

def restore_qdrant():
    if not os.path.exists(SNAPSHOT_PATH):
        logger.warning(f"No snapshot found at {SNAPSHOT_PATH}. Skipping Qdrant restore.")
        return

    logger.info(f"🚀 Restoring Qdrant collection '{COLLECTION_NAME}' from snapshot...")
    
    with httpx.Client(timeout=300.0) as client:
        # Check if collection exists
        try:
            resp = client.get(f"{QDRANT_URL}/collections/{COLLECTION_NAME}")
            if resp.status_code == 200:
                # Optional: Delete if you want to force restore
                # For now, let's only restore if it doesn't exist to avoid data loss on existing dev setups
                logger.info(f"Collection '{COLLECTION_NAME}' already exists. Skipping restore to avoid overwrite.")
                return
        except:
            pass

        # 1. Upload snapshot (this is easier than mounting if we want true portability)
        # Note: Qdrant's 'recover from snapshot' API can take a URL or a path inside the container.
        # Since we use 'docker cp' in backup, easiest is 'docker cp' + API call.
        
        try:
            # Copy snapshot into the container temp dir
            import subprocess
            subprocess.run(["docker", "cp", SNAPSHOT_PATH, f"cinesense-qdrant:/tmp/restore.snapshot"], check=True)
            
            # Trigger recovery
            resp = client.post(
                f"{QDRANT_URL}/collections/{COLLECTION_NAME}/snapshots/recover",
                json={"location": "file:///tmp/restore.snapshot"}
            )
            resp.raise_for_status()
            logger.success(f"Successfully triggered recovery for '{COLLECTION_NAME}'")
            
        except Exception as e:
            logger.error(f"Failed to restore Qdrant: {e}")

if __name__ == "__main__":
    if wait_for_qdrant():
        restore_qdrant()
