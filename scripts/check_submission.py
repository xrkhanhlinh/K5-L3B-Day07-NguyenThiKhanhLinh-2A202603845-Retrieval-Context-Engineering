"""Recompute submission metrics, frozen hashes, source offsets and trace boundaries."""
import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import ROOT, digest, load, now, save
from src.evaluate import agent_summary, evidence_hit, retrieval_summary, score_context


def main():
    frozen = load(ROOT / "benchmark/frozen_inputs.json")
    for relative, expected in frozen["sha256"].items():
        assert digest(ROOT / relative) == expected, relative
    selection = load(ROOT / "results/selection.json")
    for relative, expected in selection["implementation_sha256"].items():
        assert digest(ROOT / relative) == expected, relative
    cases = load(ROOT / "benchmark/cases.json")
    chunks = {c["id"]: c for c in load(ROOT / "data/day6/chunks.json")}
    vectors = load(ROOT / "data/day6/vectors.json")
    assert vectors["chunk_export_sha256"] == digest(ROOT / "data/day6/chunks.json")
    assert {p["id"] for p in vectors["points"]} == set(chunks)
    assert len(vectors["points"]) == len(chunks)
    assert all(len(p["vector"]) == 384 and any(p["vector"]) and all(math.isfinite(x) for x in p["vector"]) for p in vectors["points"])
    pages = {p["page"]: p for p in (json.loads(line) for line in (ROOT / "data/day6/pages.jsonl").read_text(encoding="utf-8").splitlines())}
    for c in chunks.values():
        assert pages[c["page"]]["text"][c["metadata"]["start"]:c["metadata"]["end"]] == c["text"], c["id"]
    for q in cases:
        for gold in q["gold"]:
            assert gold["evidence"] in pages[gold["page"]]["text"]
            assert any(evidence_hit(c, [gold]) for c in chunks.values()), q["id"]
    selected = selection["selected_config"]
    for split in ("dev", "test"):
        cached = load(ROOT / f"artifacts/query_vectors_{split}.json")
        assert {r["question"] for r in cached["queries"]} == {q["question"] for q in cases if q["split"] == split}
        assert all(len(r["vector"]) == 384 and all(math.isfinite(x) for x in r["vector"]) for r in cached["queries"])
        if split == "test":
            assert cached["created_at_utc"] > selection["selected_at_utc_before_test"]
    expected_folders = [("dev", c["name"]) for c in load(ROOT / "benchmark/protocol.json")["configs"]]
    expected_folders += [("test", name) for name in dict.fromkeys(["dense", selected])]
    counts = {"retrieval_traces": 0, "agent_traces": 0, "model_calls": 0, "errors": 0, "reviews": 0}
    for split, name in expected_folders:
        folder = ROOT / "results" / split / name
        selected_cases = [q for q in cases if q["split"] == split]
        lookup = {q["id"]: q for q in selected_cases}
        retrieval = load(folder / "retrieval.json")
        agents = load(folder / "agent.json")
        reviews = load(folder / "reviews.json")
        assert {t["query_id"] for t in agents} == set(lookup)
        assert len({t["query_id"] for t in agents}) == len(agents)
        assert len({r["query_id"] for r in reviews}) == len(reviews)
        assert retrieval_summary(retrieval) == load(folder / "retrieval_summary.json")
        recomputed = json.loads(json.dumps(agent_summary(selected_cases, agents, reviews)))
        assert recomputed == load(folder / "agent_summary.json"), f"Summary differs: {split}/{name}"
        for trace in retrieval:
            q = lookup[trace["query_id"]]
            if split == "test":
                assert trace["completed_at_utc"] > selection["selected_at_utc_before_test"]
            assert trace["question"] == q["question"]
            if q["answerable"]:
                assert trace["hit1"] == bool(trace["results"] and evidence_hit(trace["results"][0], q["gold"]))
                assert trace["hit3"] == any(evidence_hit(c, q["gold"]) for c in trace["results"][:3])
        for trace in agents:
            q = lookup[trace["query_id"]]
            if split == "test":
                assert trace["completed_at_utc"] > selection["selected_at_utc_before_test"]
            assert len(trace["context"]) <= next(c["budget"] for c in load(ROOT / "benchmark/protocol.json")["configs"] if c["name"] == name)
            assert len({c["id"] for c in trace["context_rows"]}) == len(trace["context_rows"])
            if q["answerable"]:
                assert trace["context_hit"] == score_context(trace["context_rows"], q)
            for row in trace["context_rows"]:
                assert row["text"] == chunks[row["id"]]["text"]
            for citation in trace["citations"]:
                assert citation in {row["id"] for row in trace["context_rows"]}
                assert f"[{citation}]" in trace["answer"]
            for event in trace["events"]:
                if event["event"] == "model":
                    counts["model_calls"] += 1
                    # Gold data keys are never serialized into the controller messages.
                    request = json.dumps(event["messages"])
                    assert '"expected_answer"' not in request and '"gold"' not in request
                if event["event"] == "search":
                    assert event["query"] == q["question"] and event["filter"] == q.get("filter", {})
            if trace["context"] and trace["status"] != "error":
                final_model = [event for event in trace["events"] if event["event"] == "model"][-1]
                assert trace["context"] in final_model["messages"][-1]["content"]
            counts["errors"] += trace["status"] == "error"
        counts["retrieval_traces"] += len(retrieval)
        counts["agent_traces"] += len(agents)
        counts["reviews"] += len(reviews)
    missing_links = []
    for document in [ROOT / "README.md", ROOT / "report/individual/2A202603845_NguyenThiKhanhLinh.md"]:
        text = document.read_text(encoding="utf-8")
        text = re.sub(r"```[\s\S]*?```", "", text)
        for target in re.findall(r"\]\(([^)]+)\)", text):
            if "://" not in target and not target.startswith("#"):
                resolved = (document.parent / target.split("#")[0]).resolve()
                if resolved != (ROOT / "results/verification.json").resolve() and not resolved.exists():
                    missing_links.append({"file": str(document.relative_to(ROOT)), "target": target})
    assert not missing_links, missing_links
    save(ROOT / "results/verification.json", {"verified_at_utc": now(), "checks":
        "Frozen input/source hashes; dev/test counts; source offsets; real Day6 vector IDs/dimensions; recomputed retrieval and reviewed-agent metrics; citations; budgets; query/filter isolation; selection before test; local links",
        "chunks": len(chunks), "cases": len(cases), **counts,
        "human_review": "Pending student/independent human confirmation; reviews are explicitly attributed to Codex AI",
        "advanced_challenge": "Not attempted; no bonus claimed", "missing_local_links": missing_links})
    print(json.dumps(counts, indent=2))


if __name__ == "__main__":
    main()
