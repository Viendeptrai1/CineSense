"""
Aspect-Based Sentiment Analysis model: RoBERTa backbone + multi-label head.

Training and inference for (aspect, sentiment) prediction on movie reviews.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModel, AutoTokenizer

from etl_pipeline.config import settings
from training.models.absa_schema import (
    NUM_LABELS,
    build_label_map,
    get_label_index,
    index_to_aspect_sentiment,
)


class AbsaDataset(Dataset):
    def __init__(
        self,
        path: Path,
        tokenizer,
        max_length: int = 128,
    ):
        self.samples = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                text = (obj.get("text") or "").strip()
                labels_raw = obj.get("labels") or []
                if not text:
                    continue
                label_vec = [0.0] * NUM_LABELS
                for item in labels_raw:
                    a = item.get("aspect")
                    s = item.get("sentiment")
                    if a and s:
                        try:
                            idx = get_label_index(a, s)
                            label_vec[idx] = 1.0
                        except ValueError:
                            pass
                self.samples.append((text, label_vec))
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, i: int):
        text, label_vec = self.samples[i]
        enc = self.tokenizer(
            text,
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        return {
            "input_ids": enc["input_ids"].squeeze(0),
            "attention_mask": enc["attention_mask"].squeeze(0),
            "labels": torch.tensor(label_vec, dtype=torch.float32),
        }


class AbsaClassifier(nn.Module):
    def __init__(self, model_name: str, num_labels: int = NUM_LABELS):
        super().__init__()
        self.backbone = AutoModel.from_pretrained(model_name)
        hidden = self.backbone.config.hidden_size
        self.head = nn.Linear(hidden, num_labels)
        self.num_labels = num_labels

    def forward(self, input_ids, attention_mask):
        out = self.backbone(input_ids=input_ids, attention_mask=attention_mask)
        cls = out.last_hidden_state[:, 0, :]
        return self.head(cls)

    @classmethod
    def from_pretrained(cls, artifact_dir: Path | str) -> "AbsaClassifier":
        """Load backbone + tokenizer from artifact_dir and head from head.pt."""
        artifact_dir = Path(artifact_dir)
        schema_path = artifact_dir / "schema.json"
        num_labels = NUM_LABELS
        if schema_path.exists():
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            num_labels = schema.get("num_labels", NUM_LABELS)
        backbone = AutoModel.from_pretrained(str(artifact_dir))
        hidden = backbone.config.hidden_size
        model = cls.__new__(cls)
        nn.Module.__init__(model)  # required before assigning submodules
        model.backbone = backbone
        model.head = nn.Linear(hidden, num_labels)
        model.num_labels = num_labels
        head_path = artifact_dir / "head.pt"
        if head_path.exists():
            model.head.load_state_dict(torch.load(head_path, map_location="cpu", weights_only=True))
        return model


def load_absa_artifact(artifact_dir: Path | str):
    """Load model, tokenizer, and schema from artifact dir. Returns (model, tokenizer, schema_dict)."""
    artifact_dir = Path(artifact_dir)
    model = AbsaClassifier.from_pretrained(artifact_dir)
    tokenizer = AutoTokenizer.from_pretrained(str(artifact_dir))
    schema = {}
    if (artifact_dir / "schema.json").exists():
        schema = json.loads((artifact_dir / "schema.json").read_text(encoding="utf-8"))
    return model, tokenizer, schema


def predict_aspects(
    model: AbsaClassifier,
    tokenizer,
    texts: list[str],
    device: torch.device,
    max_length: int = 128,
    threshold: float = 0.5,
) -> list[list[dict]]:
    """Run inference; return per-text list of {aspect, sentiment, score}."""
    model.eval()
    results = []
    with torch.no_grad():
        for text in texts:
            enc = tokenizer(
                text,
                max_length=max_length,
                padding="max_length",
                truncation=True,
                return_tensors="pt",
            )
            input_ids = enc["input_ids"].to(device)
            attention_mask = enc["attention_mask"].to(device)
            logits = model(input_ids, attention_mask).squeeze(0)
            probs = torch.sigmoid(logits).cpu().numpy()
            items = []
            for idx, p in enumerate(probs):
                if p >= threshold:
                    aspect, sentiment = index_to_aspect_sentiment(idx)
                    items.append({"aspect": aspect, "sentiment": sentiment, "score": round(float(p), 4)})
            results.append(items)
    return results


def train(
    labeled_path: Path,
    artifact_dir: Path,
    model_name: str | None = None,
    batch_size: int = 8,
    epochs: int = 3,
    lr: float = 2e-5,
    max_length: int = 128,
) -> dict:
    model_name = model_name or settings.absa.model_name
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    dataset = AbsaDataset(labeled_path, tokenizer, max_length=max_length)
    if len(dataset) == 0:
        raise ValueError(f"No samples in {labeled_path}")

    loader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=0,
    )
    model = AbsaClassifier(model_name, NUM_LABELS).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=lr)
    criterion = nn.BCEWithLogitsLoss()

    model.train()
    for epoch in range(epochs):
        total_loss = 0.0
        for batch in loader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)
            opt.zero_grad()
            logits = model(input_ids, attention_mask)
            loss = criterion(logits, labels)
            loss.backward()
            opt.step()
            total_loss += loss.item()
        print(f"Epoch {epoch + 1}/{epochs} loss: {total_loss / len(loader):.4f}")

    artifact_dir.mkdir(parents=True, exist_ok=True)
    model.backbone.save_pretrained(artifact_dir)
    tokenizer.save_pretrained(artifact_dir)
    torch.save(model.head.state_dict(), artifact_dir / "head.pt")

    schema = {
        "aspects": list(build_label_map()),
        "num_labels": NUM_LABELS,
    }
    (artifact_dir / "schema.json").write_text(
        json.dumps(schema, indent=2),
        encoding="utf-8",
    )
    metadata = {
        "model_name": model_name,
        "dataset_size": len(dataset),
        "epochs": epochs,
        "batch_size": batch_size,
        "created_at": datetime.now(UTC).isoformat(),
    }
    (artifact_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description="Train ABSA model on labeled JSONL.")
    parser.add_argument(
        "--labeled",
        type=Path,
        default=Path("Notebook_Report/absa/labeled_absa_auto.jsonl"),
        help="Path to labeled JSONL",
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("Notebook_Report/absa/artifacts/absa_bert_tiny_latest"),
        help="Output artifact directory",
    )
    parser.add_argument("--model", type=str, default=None, help="HF model name (default: from config)")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--lr", type=float, default=2e-5)
    args = parser.parse_args()

    if not args.labeled.exists():
        print(f"Labeled file not found: {args.labeled}")
        print("Use Notebook_Report/03b_ABSA_AutoLabeling.ipynb to generate labeled JSONL first.")
        return

    meta = train(
        labeled_path=args.labeled,
        artifact_dir=args.artifact_dir,
        model_name=args.model,
        batch_size=args.batch_size,
        epochs=args.epochs,
        lr=args.lr,
    )
    print(f"Artifacts saved to {args.artifact_dir}")
    print("Metadata:", meta)


if __name__ == "__main__":
    main()
