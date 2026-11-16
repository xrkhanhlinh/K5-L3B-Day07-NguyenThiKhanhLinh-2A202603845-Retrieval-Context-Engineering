"""Serialize explicit AI source-review annotations; never infer answer grades from hits."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import ROOT, load, now, save


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--notes", required=True, type=Path)
    parser.add_argument("--split", required=True, choices=("dev", "test"))
    args = parser.parse_args()
    notes = load(args.notes)
    cases = {q["id"]: q for q in load(ROOT / "benchmark/cases.json") if q["split"] == args.split}
    for name, annotations in notes.items():
        folder = ROOT / "results" / args.split / name
        traces = {t["query_id"]: t for t in load(folder / "agent.json")}
        if {n["id"] for n in annotations} != set(traces):
            raise ValueError(f"Incomplete explicit annotations for {name}")
        reviews = []
        for note in annotations:
            trace = traces[note["id"]]
            if trace["status"] == "error":
                continue
            rows = {c["id"]: c for c in trace["context_rows"]}
            supported = note["support_aliases"]
            available_citations = {rows[cid]["alias"] for cid in trace["citations"]}
            if not set(supported).issubset(available_citations):
                raise ValueError(f"Review supports a citation not in answer: {name}/{note['id']}")
            citation_reviews = []
            for cid in trace["citations"]:
                row = rows[cid]
                alias = row["alias"]
                quote = note.get("quotes", {}).get(alias)
                if quote is not None and quote not in row["text"]:
                    raise ValueError(f"Reviewer quote not in source {name}/{note['id']}/{alias}")
                citation_reviews.append({"citation_id": cid, "alias": alias, "page": row["page"],
                    "support": alias in supported, "evidence_quote": quote,
                    "reason": note.get("citation_reasons", {}).get(alias, note["reason"])})
            review = {"query_id": note["id"], "reviewed_at_utc": now(),
                "reviewer": "Codex AI read answer and source excerpts; independent human confirmation pending",
                "citation_support": [r["support"] for r in citation_reviews], "citation_reviews": citation_reviews,
                "reason": note["reason"], "context_grade": note.get("context_grade"),
                "context_reason": note.get("context_reason", note["reason"]), "human_confirmed": False}
            if cases[note["id"]]["answerable"]:
                review["answer_grade"] = note["answer_grade"]
            else:
                review["abstention_correct"] = note["abstention_correct"]
            reviews.append(review)
        save(folder / "reviews.json", reviews)
        print(f"Saved {len(reviews)} explicitly annotated reviews for {name}")
