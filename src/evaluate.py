"""Separate exact-evidence retrieval evaluation from reviewed semantic answer grading."""
import statistics
import time
from collections import Counter

from .retrieval import pack_context


def evidence_hit(chunk, gold):
    return any(chunk["source_id"] == g["source_id"] and chunk["page"] == g["page"] and g["evidence"] in chunk["text"] for g in gold)


def score_context(rows, case):
    return any(evidence_hit(row, case.get("gold", [])) for row in rows)


def evaluate_retrieval(engine, case, config):
    tick = time.perf_counter()
    rows = engine.search(case["question"], config["method"], case.get("filter", {}), max(3, config["top_k"]))
    seconds = time.perf_counter() - tick
    context, selected = pack_context(rows[:config["top_k"]], config["budget"])
    answerable = case["answerable"]
    marked = [{**row, "evidence_hit": evidence_hit(row, case.get("gold", [])) if answerable else None} for row in rows]
    return {"query_id": case["id"], "question": case["question"], "split": case["split"],
            "config": config["name"], "answerable": answerable, "applied_filter": case.get("filter", {}),
            "query_policy": "original", "results": marked, "context": context,
            "context_ids": [row["id"] for row in selected], "context_chars": len(context),
            "hit1": bool(marked and marked[0]["evidence_hit"]) if answerable else None,
            "hit3": any(row["evidence_hit"] for row in marked[:3]) if answerable else None,
            "context_hit": score_context(selected, case) if answerable else None,
            "elapsed_seconds": seconds, "service_cost_usd": 0}


def ratio(n, N):
    return {"n": n, "N": N, "rate": n / N if N else None}


def retrieval_summary(traces):
    valid = [t for t in traces if t["answerable"]]
    return {"cases": len(traces), "hit1": ratio(sum(t["hit1"] for t in valid), len(valid)),
            "hit3": ratio(sum(t["hit3"] for t in valid), len(valid)),
            "context_evidence_rate": ratio(sum(t["context_hit"] for t in valid), len(valid)),
            "total_seconds": sum(t["elapsed_seconds"] for t in traces),
            "median_ms": statistics.median(t["elapsed_seconds"] * 1000 for t in traces),
            "mean_context_chars": statistics.mean(t["context_chars"] for t in traces), "service_cost_usd": 0}


def agent_summary(cases, traces, reviews):
    lookup = {q["id"]: q for q in cases}
    labels = {r["query_id"]: r for r in reviews}
    successful = [t for t in traces if t["status"] != "error"]
    for t in successful:
        if t["query_id"] not in labels:
            raise ValueError(f"Missing review for {t['query_id']}")
    answerable = [t for t in successful if lookup[t["query_id"]]["answerable"]]
    missing = [t for t in successful if not lookup[t["query_id"]]["answerable"]]
    grades = Counter(labels[t["query_id"]]["answer_grade"] for t in answerable)
    citation_n = citation_N = 0
    for t in successful:
        support = labels[t["query_id"]]["citation_support"]
        if len(support) != len(t["citations"]) or any(type(s) is not bool for s in support):
            raise ValueError("A reviewed support boolean is required for every citation")
        if lookup[t["query_id"]]["answerable"]:
            grade = labels[t["query_id"]]["answer_grade"]
            if type(grade) is not int or grade not in (0, 1, 2) or (t["status"] == "abstain" and grade != 0):
                raise ValueError("Invalid grounded answer grade")
        citation_n += sum(support)
        citation_N += len(support)
    return {"cases": len(traces), "errors": len(traces) - len(successful),
            "tool_use": ratio(sum(any(e["event"] == "search" for e in t["events"]) for t in successful), len(successful)),
            "search_count_distribution": dict(Counter(sum(e["event"] == "search" for e in t["events"]) for t in successful)),
            "grounded_answer": {"0": grades[0], "1": grades[1], "2": grades[2], "N": len(answerable),
                                "mean_out_of_2": (grades[1] + 2 * grades[2]) / len(answerable) if answerable else None},
            "context_evidence_rate": ratio(sum(t["context_hit"] for t in answerable), len(answerable)),
            "context_grades": dict(Counter(labels[t["query_id"]]["context_grade"] for t in answerable)),
            "citation_validity": ratio(citation_n, citation_N),
            "answer_citation_coverage": ratio(sum(bool(t["citations"]) for t in successful if t["status"] == "answered"),
                                              sum(t["status"] == "answered" for t in successful)),
            "abstention": ratio(sum(labels[t["query_id"]]["abstention_correct"] for t in missing), len(missing)),
            "false_abstention": ratio(sum(t["status"] == "abstain" for t in answerable), len(answerable)),
            "total_seconds": sum(t["elapsed_seconds"] for t in traces),
            "prompt_tokens": sum(e.get("usage", {}).get("prompt_tokens", 0) for t in traces for e in t["events"]),
            "completion_tokens": sum(e.get("usage", {}).get("completion_tokens", 0) for t in traces for e in t["events"]),
            "service_cost_usd": 0, "reviewer": "Codex AI source reading; student/independent human confirmation pending"}
