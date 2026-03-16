"""
Gán nhãn ABSA tự động cho dữ liệu chưa gán nhãn.

- Phát hiện aspect bằng từ khóa (script, acting, visuals, music, pacing, direction).
- Luôn thêm aspect "overall".
- Sentiment bằng VADER (positive/negative/neutral) gán cho mỗi aspect phát hiện được.

Chạy:
  python -m training.data.absa_auto_label --input training/data/absa/absa_unlabeled.jsonl --output training/data/absa/labeled_absa_auto.jsonl
  python -m training.data.absa_auto_label --input training/data/absa/absa_unlabeled.jsonl --output training/data/absa/labeled_absa_auto.jsonl --limit 500
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from training.models.absa_schema import ASPECTS, SENTIMENTS

# Từ khóa theo aspect (chỉ 6 aspect; overall thêm sau)
ASPECT_KEYWORDS: dict[str, list[str]] = {
    "script": [
        "script", "story", "plot", "writing", "written", "screenplay", "narrative",
        "storyline", "dialogue", "dialog", "scriptwriter",
    ],
    "acting": [
        "acting", "performance", "performances", "actor", "actress", "cast",
        "starring", "played", "portrayal", "character",
    ],
    "visuals": [
        "visual", "visuals", "cgi", "cinematography", "cinematic", "look", "effects",
        "special effects", "animation", "animated", "cinematographer", "shot", "shots",
    ],
    "music": [
        "music", "score", "soundtrack", "sound track", "musical", "song", "songs",
        "composer", "composer",
    ],
    "pacing": [
        "pacing", "pace", "slow", "fast", "drag", "dragged", "rushed", "length",
        "long", "short", "boring", "tedious", "tight", "flow",
    ],
    "direction": [
        "direction", "director", "directed", "filmmaking", "film-making",
        "helmed", "directorial",
    ],
}


def _normalize_for_keyword(s: str) -> str:
    """Chuẩn hóa để so khớp từ khóa (lowercase, chỉ chữ)."""
    return re.sub(r"[^a-z\s]", " ", s.lower())


def detect_aspects(text: str) -> set[str]:
    """
    Trả về set các aspect được nhắc đến trong text (theo từ khóa).
    Luôn thêm 'overall'.
    """
    normalized = _normalize_for_keyword(text)
    words = set(normalized.split())
    found: set[str] = {"overall"}
    for aspect, keywords in ASPECT_KEYWORDS.items():
        for kw in keywords:
            if kw in words or kw in normalized:
                found.add(aspect)
                break
    return found


def get_sentiment_vader(text: str) -> str:
    """
    Trả về sentiment (positive | neutral | negative) dựa trên VADER.
    Dùng ngưỡng compound: <= -0.05 negative, >= 0.05 positive, còn lại neutral.
    """
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        analyzer = SentimentIntensityAnalyzer()
        scores = analyzer.polarity_scores(text)
        compound = scores["compound"]
        if compound <= -0.05:
            return "negative"
        if compound >= 0.05:
            return "positive"
        return "neutral"
    except ImportError:
        # Fallback: heuristic đơn giản (từ tích cực/tiêu cực thường gặp)
        return _fallback_sentiment(text)


def _fallback_sentiment(text: str) -> str:
    """Fallback khi không có vaderSentiment."""
    t = text.lower()
    pos = ("great", "good", "amazing", "excellent", "love", "best", "brilliant", "stunning", "outstanding", "positive")
    neg = ("bad", "terrible", "weak", "boring", "worst", "awful", "poor", "disappointing", "negative", "do not recommend")
    has_pos = sum(1 for w in pos if w in t)
    has_neg = sum(1 for w in neg if w in t)
    if has_pos > has_neg:
        return "positive"
    if has_neg > has_pos:
        return "negative"
    return "neutral"


def auto_label_record(record: dict, sentiment_fn=None) -> dict:
    """
    Thêm trường 'labels' vào record (unlabeled).
    sentiment_fn(text) -> "positive"|"neutral"|"negative". Mặc định dùng VADER.
    """
    text = record.get("text", "")
    if not text or not text.strip():
        record["labels"] = []
        return record
    sentiment_fn = sentiment_fn or get_sentiment_vader
    sentiment = sentiment_fn(text)
    if sentiment not in SENTIMENTS:
        sentiment = "neutral"
    aspects = detect_aspects(text)
    record["labels"] = [{"aspect": a, "sentiment": sentiment} for a in sorted(aspects)]
    return record


def run(
    input_path: Path,
    output_path: Path,
    limit: int | None = None,
) -> int:
    """
    Đọc JSONL chưa gán nhãn, gán nhãn tự động, ghi ra JSONL đã gán nhãn.
    Trả về số dòng đã ghi.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with open(input_path, "r", encoding="utf-8") as fin, open(output_path, "w", encoding="utf-8") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            auto_label_record(record)
            fout.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
            if limit is not None and count >= limit:
                break
    return count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gán nhãn ABSA tự động (keyword + VADER sentiment) cho file JSONL chưa gán nhãn."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("training/data/absa/absa_unlabeled.jsonl"),
        help="Đường dẫn file JSONL chưa gán nhãn",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("training/data/absa/labeled_absa_auto.jsonl"),
        help="Đường dẫn file JSONL đã gán nhãn (ghi đè nếu có)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Số dòng tối đa xử lý (mặc định: tất cả)",
    )
    args = parser.parse_args()

    if not args.input.exists():
        print(f"File không tồn tại: {args.input}")
        print("Chạy trước: python -m training.data.absa_prepare --output", args.input, "[--limit N]")
        raise SystemExit(1)

    n = run(input_path=args.input, output_path=args.output, limit=args.limit)
    print(f"Đã gán nhãn tự động {n} mẫu -> {args.output}")
    print("Có thể train ABSA với: python -m training.models.absa_model --labeled", args.output)


if __name__ == "__main__":
    main()
