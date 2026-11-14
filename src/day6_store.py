"""Real Day 6 MiniLM embeddings and verified persistent Chroma snapshot."""
import argparse
import hashlib
import json
import os
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL = "sentence-transformers/all-MiniLM-L6-v2"
REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
DIM = 384


@lru_cache(maxsize=1)
def encoder():
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    import torch
    from sentence_transformers import SentenceTransformer
    torch.set_num_threads(4)
    model = SentenceTransformer(str(ROOT / ".cache/all-MiniLM-L6-v2"), device="cpu", local_files_only=True)
    if model.get_sentence_embedding_dimension() != DIM:
        raise ValueError("Day 6 encoder must produce 384 dimensions")
    return model


def embed(text):
    return encoder().encode([text], normalize_embeddings=True, show_progress_bar=False)[0].tolist()


def corpus_hash(chunks):
    return hashlib.sha256(json.dumps(chunks, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def open_collection(path, name="day06_b"):
    import chromadb
    from chromadb.config import Settings
    client = chromadb.PersistentClient(path=str(path), settings=Settings(anonymized_telemetry=False))
    return client.get_collection(name, embedding_function=None)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunks", type=Path, default=ROOT / "data/chunks.json")
    parser.add_argument("--output", type=Path, default=ROOT / "src/day6_index.json")
    parser.add_argument("--store", type=Path, default=ROOT / ".cache/day6_store")
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    chunks = json.loads(args.chunks.read_text(encoding="utf-8"))
    if args.rebuild:
        import chromadb
        from chromadb.config import Settings
        client = chromadb.PersistentClient(path=str(args.store), settings=Settings(anonymized_telemetry=False))
        collection = client.get_or_create_collection("day06_b", embedding_function=None,
            metadata={"hnsw:space": "cosine", "hnsw:search_ef": 100, "embedding_dimensions": DIM})
        vectors = encoder().encode([c["text"] for c in chunks], normalize_embeddings=True,
                                   batch_size=32, show_progress_bar=False).tolist()
        for start in range(0, len(chunks), 128):
            batch = chunks[start:start + 128]
            collection.upsert(ids=[c["id"] for c in batch], documents=[c["text"] for c in batch],
                embeddings=vectors[start:start + 128], metadatas=[{**c["metadata"],
                    "document_id": c["source_id"], "source": c["source"], "page": c["page"]} for c in batch])
        old = set(collection.get(include=[])["ids"]) - {c["id"] for c in chunks}
        if old:
            collection.delete(ids=sorted(old))
    collection = open_collection(args.store)
    data = collection.get(include=["embeddings", "documents", "metadatas"])
    rows = {cid: (v, text, meta) for cid, v, text, meta in zip(
        data["ids"], data["embeddings"], data["documents"], data["metadatas"])}
    if set(rows) != {c["id"] for c in chunks}:
        raise ValueError("Store IDs differ from Day 6 B snapshot")
    vectors = []
    for c in chunks:
        vector, text, meta = rows[c["id"]]
        if text != c["text"] or meta["page"] != c["page"] or len(vector) != DIM:
            raise ValueError("Snapshot provenance or dimension mismatch")
        vectors.append({"id": c["id"], "vector": vector.tolist()})
    result = {"embedding_model": MODEL, "revision": REVISION, "dim": DIM,
              "max_seq_length": 256, "normalize_embeddings": True, "collection": "day06_b",
              "backend": "Chroma cosine HNSW", "corpus_sha256": corpus_hash(chunks), "vectors": vectors}
    args.output.write_text(json.dumps(result) + "\n", encoding="utf-8")
    print(f"Verified {len(vectors)} actual Day 6 vectors, dimension={DIM}")


if __name__ == "__main__":
    main()
