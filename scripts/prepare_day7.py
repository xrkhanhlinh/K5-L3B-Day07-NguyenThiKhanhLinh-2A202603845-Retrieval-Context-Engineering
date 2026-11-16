"""Freeze a permitted Day 6 snapshot and a new Day 7 benchmark, before retrieval."""
import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import ROOT, digest, load, now, save


def prepare(day6):
    target = ROOT / "data/day6"
    if (ROOT / "results/selection.json").exists():
        raise RuntimeError("Refusing to replace benchmark after selection; use a fresh experiment directory.")
    target.mkdir(parents=True, exist_ok=True)
    for relative in ("data/pages.jsonl", "data/manifest.json", "data/raw/pg11.txt", "results/run_info.json"):
        source = day6 / relative
        destination = target / Path(relative).name
        shutil.copy2(source, destination)
    rows = [json.loads(line) for line in (day6 / "results/chunks.jsonl").read_text(encoding="utf-8").splitlines()]
    chunks = [{"id": c["chunk_id"], "source_id": c["document_id"], "source": c["source"],
               "page": c["page"], "text": c["text"], "metadata": c["metadata"]}
              for c in rows if c["strategy"] == "C"]
    save(target / "chunks.json", chunks)
    # Copy a closed local database, not vectors recomputed with a different encoder.
    database = ROOT / ".qdrant"
    if database.exists():
        raise RuntimeError("Local .qdrant already exists; do not overwrite an experiment database.")
    shutil.copytree(day6 / ".qdrant", database, ignore=shutil.ignore_patterns(".lock"))
    if not (ROOT / ".model_cache").exists():
        shutil.copytree(day6 / ".model_cache", ROOT / ".model_cache")
    old = load(day6 / "benchmark/questions.json")
    cases = []
    for q in old:
        if q["split"] != "dev":
            continue
        cases.append({"id": "d" + q["id"][1:], "split": "dev", "answerable": True,
                      "question": q["question"], "expected_answer": q["expected_answer"],
                      "filter": q.get("filter", {}), "filter_origin": "User-supplied chapter scope in original Day 6 question",
                      "gold": [{"source_id": q["gold_source_id"], "page": q["gold_page"], "evidence": q["evidence_quote"]}],
                      "provenance": "Day 6 dev retained; Day 6 test excluded"})
    # Additional source-valid evidence identified during explicit Day 7 dev audit.
    for case in cases:
        if case["id"] == "d10":
            case["gold"].append({"source_id": "alice-1865", "page": 20, "evidence": "“Serpent!” screamed the Pigeon."})
            case["gold"].append({"source_id": "alice-1865", "page": 20,
                "evidence": "“A likely story indeed!” said the Pigeon in a tone of the deepest contempt."})
        if case["id"] == "d11":
            case["gold"].append({"source_id": "alice-1865", "page": 25, "evidence": "“It turned into a pig,” Alice quietly said"})
    new_test = [
        ("t01", "Who does the Queen order to take Alice to see the Mock Turtle?", "The Gryphon.", 38,
         "“Up, lazy thing!” said the Queen, “and take this young lady to see the Mock Turtle, and to hear his history.", {}),
        ("t02", "In The Lobster Quadrille, how many lines do the dancers form at the start?", "Two lines.", 41,
         "“Two lines!” cried the Mock Turtle.", {"chapter": "X"}),
        ("t03", "Why do the jurors write down their names before the trial begins?", "For fear they will forget them before the trial ends.", 45,
         "“They’re putting down their names,” the Gryphon whispered in reply, “for fear they should forget them before the end of the trial.”", {}),
        ("t04", "In Alice’s Evidence, what height does Rule Forty-two say requires a person to leave the court?", "More than a mile high.", 49,
         "Rule Forty-two. _All persons more than a mile high to leave the court_", {"chapter": "XII"}),
        ("t05", "Where is Alice's head resting when she wakes from the dream?", "In her sister's lap.", 52,
         "found herself lying on the bank, with her head in the lap of her sister", {}),
    ]
    for cid, question, answer, page, evidence, filters in new_test:
        cases.append({"id": cid, "split": "test", "answerable": True, "question": question,
                      "expected_answer": answer, "gold": [{"source_id": "alice-1865", "page": page, "evidence": evidence}],
                      "filter": filters, "filter_origin": "Explicit chapter title in question" if filters else "No filter",
                      "provenance": "New Day 7 fact; not a paraphrase of any Day 6 benchmark answer"})
    missing = [
        ("d16", "dev", "What is the White Rabbit's exact annual salary in pounds?", "Rabbit salary / annual pay / pounds"),
        ("d17", "dev", "What is the Cheshire Cat's exact date of birth, including day, month and year?", "Cheshire Cat birthday / date of birth"),
        ("t06", "test", "What is the Queen of Hearts' personal telephone number?", "Queen phone / telephone number"),
        ("t07", "test", "What is the Mock Turtle's exact home street address and house number?", "Mock Turtle address / street / house number"),
    ]
    for cid, split, question, search in missing:
        cases.append({"id": cid, "split": split, "answerable": False, "question": question,
                      "expected_behavior": "search_and_abstain", "filter": {}, "gold": [],
                      "absence_reason": "Corpus-wide concept scan and review of matching excerpts and character scenes found no requested exact datum. See benchmark/absence_audit.json; independent human confirmation pending.",
                      "absence_check": search + "; all-unit scan and character-context inspection, not top-k absence alone"})
    pages = [json.loads(line) for line in (target / "pages.jsonl").read_text(encoding="utf-8").splitlines()]
    for q in cases:
        for g in q["gold"]:
            assert any(p["page"] == g["page"] and p["document_id"] == g["source_id"] and g["evidence"] in p["text"] for p in pages), q["id"]
    save(ROOT / "benchmark/cases.json", cases)
    protocol = {
        "created_at_utc": now(), "scope": "Basic 85-point task; optional advanced challenge not attempted",
        "day6_strategy": "C", "collection": "day06_C", "chunk_count": len(chunks),
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2", "dimensions": 384,
        "query_policy": "Original question on first search; no gold or expected_answer enters agent or retrievers. No rewrite in retrieval comparison.",
        "configs": [
            {"name": "dense", "method": "dense", "top_k": 3, "budget": 3200, "max_searches": 1, "hypothesis": "Baseline: reuse Day 6 dense C and explicit chapter filters."},
            {"name": "bm25", "method": "bm25", "top_k": 3, "budget": 3200, "max_searches": 1, "hypothesis": "Improvement 1: lexical matching recovers rare names and exact phrases missed by dense."},
            {"name": "hybrid", "method": "hybrid", "top_k": 3, "budget": 3200, "max_searches": 1, "hypothesis": "Improvement 2: RRF of dense and BM25 combines semantic and lexical evidence."},
            {"name": "hybrid_context", "method": "hybrid", "top_k": 6, "budget": 6200, "max_searches": 1, "hypothesis": "Improvement 3: a larger deduplicated context may retain evidence below rank 3, with increased model cost."},
        ],
        "bm25": {"k1": 1.5, "b": 0.75, "tokenization": "Unicode alphanumeric lower-case; no stemming; English corpus"},
        "rrf": {"k": 60, "candidates_per_retriever": 20, "weights": [1, 1]},
        "selection": "On dev only: maximize AI-reviewed grounded answer mean, then Context Evidence Rate, then Evidence Hit@3, then lower total measured agent seconds, then config name. Human review pending is disclosed.",
        "test_policy": "Run baseline and frozen selected config only. No test tuning. New Day 7 questions, same public-domain corpus; not an external independent benchmark.",
        "hit_definition": "A single chunk at correct source_id/page contains a full gold evidence quote. Alternative gold entries are OR; no multi-hop cases here.",
        "context_definition": "At least one valid gold evidence is wholly present in the final source-labelled context; denominator answerable cases only.",
        "model_cost": "Local API USD 0 excludes hardware/electricity/downloads; remote cost unknown unless provider prices are supplied, never assumed zero.",
    }
    save(ROOT / "benchmark/protocol.json", protocol)
    inputs = [target / "chunks.json", target / "pages.jsonl", ROOT / "benchmark/cases.json", ROOT / "benchmark/protocol.json"]
    save(ROOT / "benchmark/frozen_inputs.json", {"frozen_at_utc": now(), "sha256": {str(p.relative_to(ROOT)): digest(p) for p in inputs},
        "day6_chunk_export_sha256": digest(day6 / "results/chunks.jsonl"), "day6_run_info_sha256": digest(day6 / "results/run_info.json")})
    print(json.dumps({"chunks": len(chunks), "dev": sum(q["split"] == "dev" for q in cases), "test": sum(q["split"] == "test" for q in cases)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--day6", required=True, type=Path)
    prepare(parser.parse_args().day6.resolve())
