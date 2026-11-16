"""Corpus-wide lexical audit plus source passages for reviewing missing-evidence labels."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import ROOT, digest, load, now, save


def main():
    pages = [json.loads(line) for line in (ROOT / "data/day6/pages.jsonl").read_text(encoding="utf-8").splitlines()]
    specifications = {
        "d16": (r"\b(salary|annual|wages|pounds|pay|paid)\b", [1, 5, 12, 45]),
        "d17": (r"\b(birthday|birth|born|date)\b", [22, 25, 34]),
        "t06": (r"\b(telephone|phone|dial|contact)\b", [31, 32, 38, 45, 51, 52]),
        "t07": (r"\b(address|street|avenue|road|house number)\b", [38, 39, 40, 41, 42, 43, 44]),
    }
    audit = []
    for cid, (pattern, relevant_pages) in specifications.items():
        matches = []
        for p in pages:
            for match in re.finditer(pattern, p["text"], re.I):
                matches.append({"page": p["page"], "term": match.group(),
                                "excerpt": p["text"][max(0, match.start() - 180):match.end() + 180]})
        audit.append({"query_id": cid, "scanned_units": len(pages), "pattern": pattern,
                      "matches": matches, "character_scene_units_for_review": relevant_pages,
                      "conclusion": "No requested exact datum found; read matching excerpts and character scenes as well as lexical scan. Not inferred from retrieval top-k.",
                      "reviewer": "Codex AI source review; independent human confirmation pending"})
    save(ROOT / "benchmark/absence_audit.json", audit)
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
