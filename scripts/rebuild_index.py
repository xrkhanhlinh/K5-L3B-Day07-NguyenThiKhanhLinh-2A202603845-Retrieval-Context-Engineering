"""Recreate Qdrant from shared real Day 6 vectors; does not overwrite a database."""
import argparse
import math
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qdrant_client import QdrantClient, models
from src.common import ROOT, digest, load, now, save


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / ".qdrant")
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError("Output already exists; choose a new directory, do not overwrite a live index")
    started = time.perf_counter()
    exported = load(ROOT / "data/day6/vectors.json")
    if digest(ROOT / "data/day6/chunks.json") != exported["chunk_export_sha256"]:
        raise ValueError("Chunk export hash mismatch")
    chunks = {c["id"]: c for c in load(ROOT / "data/day6/chunks.json")}
    if {p["id"] for p in exported["points"]} != set(chunks):
        raise ValueError("Vector and chunk IDs differ")
    client = QdrantClient(path=str(args.output))
    try:
        client.create_collection("day06_C", vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE))
        points = []
        for point in exported["points"]:
            c, vector = chunks[point["id"]], point["vector"]
            if len(vector) != 384 or not all(math.isfinite(v) for v in vector) or not any(vector):
                raise ValueError("Invalid stored real vector")
            payload = {**c["metadata"], "chunk_id": c["id"], "document_id": c["source_id"],
                       "source": c["source"], "page": c["page"], "text": c["text"]}
            points.append(models.PointStruct(id=str(uuid.uuid5(uuid.NAMESPACE_URL, c["id"])), vector=vector, payload=payload))
        for index in range(0, len(points), 128):
            client.upsert("day06_C", points[index:index + 128], wait=True)
        assert client.count("day06_C", exact=True).count == len(chunks)
    finally:
        client.close()
    save(args.output / "day7_rebuild_manifest.json", {"rebuilt_at_utc": now(), "points": len(chunks),
        "real_vector_export_sha256": digest(ROOT / "data/day6/vectors.json"),
        "elapsed_seconds": time.perf_counter() - started, "service_cost_usd": 0})
    print("Recreated Day 6 index from real exported vectors:", args.output)
