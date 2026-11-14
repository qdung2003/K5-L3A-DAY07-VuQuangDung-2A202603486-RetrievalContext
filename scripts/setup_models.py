"""Download the pinned public encoder and reconstruct Chroma from exported Day 6 vectors."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--download", action="store_true", help="Download missing pinned MiniLM files")
    parser.add_argument("--store", type=Path, default=ROOT / ".cache/day6_store")
    args = parser.parse_args()
    manifest = json.loads((ROOT / "data/day6_model_manifest.json").read_text(encoding="utf-8"))
    folder = ROOT / ".cache/all-MiniLM-L6-v2"
    for name, expected in manifest["sha256"].items():
        path = folder / name
        if not path.exists() and args.download:
            url = f"https://huggingface.co/{manifest['model']}/resolve/{manifest['revision']}/{name}"
            path.parent.mkdir(parents=True, exist_ok=True)
            import requests
            with requests.get(url, stream=True, timeout=60) as response:
                response.raise_for_status()
                with path.open("wb") as stream:
                    for block in response.iter_content(1024 * 1024):
                        stream.write(block)
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Missing or changed model file: {name}; run with --download")
    import chromadb
    from chromadb.config import Settings

    from day6_store import DIM, corpus_hash
    chunks = json.loads((ROOT / "data/chunks.json").read_text(encoding="utf-8"))
    index = json.loads((ROOT / "src/day6_index.json").read_text(encoding="utf-8"))
    if index.get("corpus_sha256") != corpus_hash(chunks) or index.get("dim") != DIM:
        raise ValueError("Exported index does not match corpus or model dimension")
    vectors = {row["id"]: row["vector"] for row in index["vectors"]}
    client = chromadb.PersistentClient(path=str(args.store),
                                      settings=Settings(anonymized_telemetry=False))
    collection = client.get_or_create_collection("day06_b", embedding_function=None,
        metadata={"hnsw:space": "cosine", "hnsw:search_ef": 100, "embedding_dimensions": DIM})
    for start in range(0, len(chunks), 128):
        batch = chunks[start:start + 128]
        collection.upsert(ids=[c["id"] for c in batch], embeddings=[vectors[c["id"]] for c in batch],
                          documents=[c["text"] for c in batch], metadatas=[{**c["metadata"],
                              "document_id": c["source_id"], "source": c["source"], "page": c["page"]} for c in batch])
    old = set(collection.get(include=[])["ids"]) - set(vectors)
    if old:
        collection.delete(ids=sorted(old))
    print(f"Verified pinned encoder and restored {collection.count()} real Day 6 vectors.")


if __name__ == "__main__":
    main()
