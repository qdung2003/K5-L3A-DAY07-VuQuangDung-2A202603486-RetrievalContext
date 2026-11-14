"""Day 6 replacement: hashed-embedding vector store (offline, deterministic).

Thay cho embedding API: mỗi chunk/question được biến thành vector 256 chiều
bằng hashing trick trên token tiếng Việt (đã chuẩn hoá NFC + casefold).
Vector được L2-normalize nên cosine = dot product. Query và doc dùng CHUNG
một hàm embed -> tương thích index (yêu cầu GUIDE.md §1).

Chạy: python src/day6_store.py --chunks data/chunks.json --output src/day6_index.json
"""
import argparse
import hashlib
import json
import math
import re
import unicodedata
from pathlib import Path

DIM = 256


def tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", unicodedata.normalize("NFC", text).casefold())


def embed(text: str, dim: int = DIM) -> list[float]:
    vec = [0.0] * dim
    for tok in tokenize(text):
        h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
        vec[h % dim] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--dim", type=int, default=DIM)
    args = ap.parse_args()
    chunks = json.loads(args.chunks.read_text(encoding="utf-8"))
    index = {
        "embedding_model": "hashed-tfidf-v1 (offline, deterministic)",
        "version": "day6-v1",
        "dim": args.dim,
        "vectors": [{"id": c["id"], "vector": embed(c["text"], args.dim)} for c in chunks],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(index, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Đã index {len(chunks)} chunks, dim={args.dim} -> {args.output}")


if __name__ == "__main__":
    main()
