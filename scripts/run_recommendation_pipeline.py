#!/usr/bin/env python3
"""
End-to-end local workflow:
1) data audit
2) baseline artifact
3) improved artifact
4) evaluation
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str]) -> None:
    print(f"$ {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run CineSense recommendation pipeline.")
    parser.add_argument("--skip-sbert", action="store_true", help="Skip sentence-transformer artifact build.")
    parser.add_argument("--top-k", type=int, default=20, help="Top-k neighbors for artifact export.")
    args = parser.parse_args()

    latest_dir = Path("training/artifacts/latest")
    latest_dir.mkdir(parents=True, exist_ok=True)

    run(["python", "scripts/audit_core_data.py", "--output-json", str(latest_dir / "core_audit.json")])
    run([
        "python",
        "-m",
        "training.baselines.train_tfidf",
        "--artifact-name",
        "tfidf_latest",
        "--top-k",
        str(args.top_k),
    ])

    if not args.skip_sbert:
        run([
            "python",
            "-m",
            "training.models.train_sentence_transformer",
            "--artifact-name",
            "sbert_latest",
            "--top-k",
            str(args.top_k),
        ])
        run([
            "python",
            "-m",
            "training.evaluation.run_eval",
            "--artifact-dir",
            "training/artifacts/sbert_latest",
            "--output-json",
            "training/artifacts/sbert_latest/eval.json",
        ])
    else:
        run([
            "python",
            "-m",
            "training.evaluation.run_eval",
            "--artifact-dir",
            "training/artifacts/tfidf_latest",
            "--output-json",
            "training/artifacts/tfidf_latest/eval.json",
        ])

    print("Pipeline completed successfully.")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        print(f"Pipeline failed with exit code {error.returncode}", file=sys.stderr)
        raise
