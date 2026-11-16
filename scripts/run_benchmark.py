"""Explicit stages: retrieval dev -> agent dev -> review -> select -> held-out test."""
import argparse
import importlib.metadata
import platform
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.agent import LocalController, run_agent
from src.common import ROOT, digest, load, now, save
from src.evaluate import agent_summary, evaluate_retrieval, retrieval_summary, score_context
from src.retrieval import RetrievalEngine

RESULTS = ROOT / "results"

def verify_frozen():
    frozen = load(ROOT / "benchmark/frozen_inputs.json")
    for relative, expected in frozen["sha256"].items():
        if digest(ROOT / relative) != expected:
            raise RuntimeError(f"Frozen input changed: {relative}")


def configuration(name):
    return next(c for c in load(ROOT / "benchmark/protocol.json")["configs"] if c["name"] == name)


def run(split, kind, names):
    verify_frozen()
    protocol = load(ROOT / "benchmark/protocol.json")
    cases = [q for q in load(ROOT / "benchmark/cases.json") if q["split"] == split]
    if split == "test":
        selected = load(RESULTS / "selection.json")
        if set(names) != {"dense", selected["selected_config"]}:
            raise ValueError("Test must evaluate baseline and frozen selected config only")
        for relative, expected in selected["implementation_sha256"].items():
            if digest(ROOT / relative) != expected:
                raise RuntimeError(f"Implementation changed after selection: {relative}")
    configs = [configuration(name) for name in names]
    engine = RetrievalEngine()
    controller = LocalController()
    try:
        for config in configs:
            destination = RESULTS / split / config["name"]
            output = destination / ("retrieval.json" if kind == "retrieval" else "agent.json")
            existing = load(output) if output.exists() else []
            by_id = {t["query_id"]: t for t in existing}
            for case in cases:
                if case["id"] in by_id:
                    print(f"Retain completed {split}/{config['name']}/{case['id']}", flush=True)
                    continue
                if kind == "retrieval":
                    trace = evaluate_retrieval(engine, case, config)
                else:
                    trace = run_agent(case["question"], case.get("filter", {}), config, engine, controller)
                    trace.update({"query_id": case["id"], "question": case["question"], "split": split,
                                  "config": config["name"], "answerable": case["answerable"],
                                  "context_hit": score_context(trace["context_rows"], case) if case["answerable"] else None})
                trace["completed_at_utc"] = now()
                existing.append(trace)
                save(output, existing)
                print(f"{split}/{config['name']}/{case['id']}: {trace.get('status', trace.get('hit3'))} {trace['elapsed_seconds']:.2f}s", flush=True)
            if kind == "retrieval":
                save(destination / "retrieval_summary.json", retrieval_summary(existing))
            save(RESULTS / "run_info.json", {"last_updated_utc": now(), "python": sys.version,
                "platform": platform.platform(), "model": load(ROOT / "artifacts/local_model.json") if (ROOT / "artifacts/local_model.json").exists() else None,
                "embedding": "sentence-transformers/all-MiniLM-L6-v2", "dimensions": 384,
                "packages": {p: importlib.metadata.version(p) for p in ("fastembed", "qdrant-client", "onnxruntime", "numpy")},
                "search": "Copied Day 6 day06_C; Qdrant local exact cosine", "temperature": 0, "seed": 7,
                "cost_exclusions": "USD 0 local service fees; excludes electricity, hardware, download and installation time",
                "cache_policy": "Real query embeddings precomputed per split in separate process; agent search loads cache without ONNX to reduce RAM. Raw retrieval timings also include original dev measurements before preprocessing cache; config order/cache affect latency."})
    finally:
        engine.close()


def summarize(split, names):
    cases = [q for q in load(ROOT / "benchmark/cases.json") if q["split"] == split]
    for name in names:
        folder = RESULTS / split / name
        traces = load(folder / "agent.json")
        if {t["query_id"] for t in traces} != {q["id"] for q in cases}:
            raise ValueError("Incomplete agent run")
        reviews = load(folder / "reviews.json")
        save(folder / "agent_summary.json", agent_summary(cases, traces, reviews))


def select():
    verify_frozen()
    if (RESULTS / "selection.json").exists():
        raise RuntimeError("Selection is already frozen")
    protocol = load(ROOT / "benchmark/protocol.json")
    names = [c["name"] for c in protocol["configs"]]
    summarize("dev", names)
    rows = []
    for name in names:
        folder = RESULTS / "dev" / name
        agent = load(folder / "agent_summary.json")
        retrieval = load(folder / "retrieval_summary.json")
        if agent["errors"]:
            raise ValueError("Resolve or explicitly revise protocol for dev errors before selecting")
        rows.append({"config": name, "agent": agent, "retrieval": retrieval})
    ranked = sorted(rows, key=lambda row: (-row["agent"]["grounded_answer"]["mean_out_of_2"],
        -row["agent"]["context_evidence_rate"]["rate"], -row["retrieval"]["hit3"]["rate"],
        row["agent"]["total_seconds"], row["config"]))
    paths = [*ROOT.glob("src/*.py"), ROOT / "scripts/run_benchmark.py", ROOT / "artifacts/local_model.json"]
    save(RESULTS / "selection.json", {"selected_at_utc_before_test": now(), "selected_config": ranked[0]["config"],
        "criterion": protocol["selection"], "dev_results": rows,
        "implementation_sha256": {str(p.relative_to(ROOT)): digest(p) for p in paths},
        "benchmark_sha256": digest(ROOT / "benchmark/cases.json"),
        "review_provenance": "Codex AI; human confirmation pending, not claimed as independent human grading"})
    print("Selected on dev:", ranked[0]["config"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("retrieval", "agent", "summarize", "select"))
    parser.add_argument("--split", choices=("dev", "test"), default="dev")
    parser.add_argument("--configs", nargs="+", default=None)
    parser.add_argument("--results-dir", type=Path, default=Path("results"), help="Use a fresh folder for a new run; existing traces resume")
    args = parser.parse_args()
    args.configs = args.configs or [c["name"] for c in load(ROOT / "benchmark/protocol.json")["configs"]]
    RESULTS = (ROOT / args.results_dir).resolve()
    if not RESULTS.is_relative_to(ROOT):
        raise ValueError("Results directory must stay inside this project")
    if args.stage == "select":
        select()
    elif args.stage == "summarize":
        summarize(args.split, args.configs)
    else:
        run(args.split, args.stage, args.configs)
