"""Interactive real agent demo without benchmark answers."""
import argparse
import json

from .agent import LocalController, run_agent
from .common import ROOT, load, save
from .retrieval import RetrievalEngine


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("--config", default=None)
    parser.add_argument("--chapter", default=None)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    name = args.config or load(ROOT / "results/selection.json")["selected_config"]
    config = next(c for c in load(ROOT / "benchmark/protocol.json")["configs"] if c["name"] == name)
    engine = RetrievalEngine()
    try:
        result = run_agent(args.question, {"chapter": args.chapter} if args.chapter else {}, config, engine, LocalController())
        if args.output:
            save(args.output, result)
        print(json.dumps({k: result[k] for k in ("status", "answer", "citations", "elapsed_seconds")}, ensure_ascii=False, indent=2))
        if result["status"] == "error":
            raise RuntimeError(result["error"])
    finally:
        engine.close()
