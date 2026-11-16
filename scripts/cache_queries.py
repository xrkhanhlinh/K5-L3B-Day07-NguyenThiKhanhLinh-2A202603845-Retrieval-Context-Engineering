"""Real query embeddings, gold-free, in a separate process to reduce peak RAM."""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import ROOT, digest, load, now, save


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", required=True, choices=("dev", "test"))
    args = parser.parse_args()
    if args.split == "test" and not (ROOT / "results/selection.json").exists():
        raise RuntimeError("Precompute test queries only after selection is frozen")
    from fastembed import TextEmbedding
    tick = time.perf_counter()
    expected = next(v for k, v in load(ROOT / "data/day6/run_info.json")["model_files"].items() if k.endswith("model.onnx"))
    weights = next(p for p in (ROOT / ".model_cache").rglob("model.onnx") if digest(p) == expected)
    encoder = TextEmbedding("sentence-transformers/all-MiniLM-L6-v2", specific_model_path=str(weights.parent),
        local_files_only=True, cache_dir=str(ROOT / ".model_cache"), threads=4, providers=["CPUExecutionProvider"])
    questions = [q["question"] for q in load(ROOT / "benchmark/cases.json") if q["split"] == args.split]
    load_seconds = time.perf_counter() - tick
    tick = time.perf_counter()
    vectors = list(encoder.embed(questions))
    embedding_seconds = time.perf_counter() - tick
    save(ROOT / f"artifacts/query_vectors_{args.split}.json", {"created_at_utc": now(), "split": args.split,
        "encoder_sha256": expected, "dimensions": 384, "model_load_seconds": load_seconds,
        "embedding_seconds": embedding_seconds, "service_cost_usd": 0,
        "policy": "Only original question text enters real encoder; no answers/gold/filters; cache prevents ONNX and LLM peak RAM overlap.",
        "queries": [{"question": q, "vector": v.tolist()} for q, v in zip(questions, vectors)]})
    print(f"Cached {len(questions)} actual query embeddings, {embedding_seconds:.3f}s embedding, {load_seconds:.3f}s load")
