"""Export the actual Day 6 vectors from the copied Qdrant database for reproduction."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qdrant_client import QdrantClient
from src.common import ROOT, digest, load, now, save


if __name__ == "__main__":
    client = QdrantClient(path=str(ROOT / ".qdrant"))
    try:
        points, offset = client.scroll("day06_C", limit=1000, with_vectors=True, with_payload=True)
        chunks = load(ROOT / "data/day6/chunks.json")
        assert offset is None and {p.payload["chunk_id"] for p in points} == {c["id"] for c in chunks}
        save(ROOT / "data/day6/vectors.json", {"provenance": "Actual vectors exported from copied Day 6 day06_C; not regenerated/random",
            "exported_at_utc": now(), "dimensions": 384, "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
            "chunk_export_sha256": digest(ROOT / "data/day6/chunks.json"),
            "points": [{"id": p.payload["chunk_id"], "vector": p.vector} for p in sorted(points, key=lambda p: p.payload["chunk_id"])]})
        print(f"Exported {len(points)} real 384-dimensional vectors")
    finally:
        client.close()
