from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TrainingConfig:
    artifacts_root: Path = Path("training/artifacts")
    default_top_k: int = 20
    max_review_snippets: int = 3
    max_review_chars: int = 240
    random_seed: int = 42


config = TrainingConfig()
