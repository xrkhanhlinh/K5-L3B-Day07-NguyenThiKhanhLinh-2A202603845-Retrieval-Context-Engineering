"""Meaningful offline checks for isolation, ranking, citations and frozen benchmark."""
import json
import unittest
from pathlib import Path

from src.agent import run_agent
from src.common import ROOT, digest, load
from src.evaluate import evidence_hit, retrieval_summary
from src.retrieval import BM25, fuse, pack_context


def chunk(cid, text, page=1, chapter="I"):
    return {"id": cid, "text": text, "source_id": "book", "source": "book.txt", "page": page,
            "metadata": {"chapter": chapter}, "score": 0.5}


class RetrievalTests(unittest.TestCase):
    def test_lexical_filters_and_empty_query(self):
        rows = [chunk("one", "orange marmalade jar", chapter="I"), chunk("two", "orange orange marmalade", chapter="II")]
        index = BM25(rows)
        self.assertEqual([c["id"] for c in index.search("orange marmalade", {"chapter": "I"})], ["one"])
        self.assertEqual(index.search(""), [])
        with self.assertRaises(ValueError):
            index.search("orange", {"gold_page": 1})

    def test_rrf_deduplicates_and_uses_rank_not_raw_score(self):
        a, b = chunk("a", "alpha"), chunk("b", "beta")
        rows = fuse([{**a, "score": 1000}, b], [{**b, "score": 0.001}, a], 3)
        self.assertEqual(len(rows), 2)
        self.assertAlmostEqual(rows[0]["score"], 1 / 61 + 1 / 62)
        self.assertEqual(set(rows[0]["component_ranks"]), {"dense", "bm25"})

    def test_context_has_source_and_whole_chunks_with_budget(self):
        a = chunk("a", "short text")
        context, selected = pack_context([a, a, chunk("b", "x" * 1000)], 130)
        self.assertEqual([r["id"] for r in selected], ["a"])
        self.assertIn("source=book.txt unit=1", context)
        self.assertLessEqual(len(context), 130)

    def test_unanswerable_excluded_and_wrong_source_is_not_hit(self):
        a = chunk("a", "evidence")
        self.assertFalse(evidence_hit(a, [{"source_id": "wrong", "page": 1, "evidence": "evidence"}]))
        traces = [{"answerable": True, "hit1": False, "hit3": True, "context_hit": False,
                   "elapsed_seconds": 0.1, "context_chars": 10},
                  {"answerable": False, "hit1": None, "hit3": None, "context_hit": None,
                   "elapsed_seconds": 0.1, "context_chars": 10}]
        summary = retrieval_summary(traces)
        self.assertEqual(summary["hit3"], {"n": 1, "N": 1, "rate": 1})


class AgentBoundaryTests(unittest.TestCase):
    config = {"method": "bm25", "top_k": 3, "budget": 1000}

    def test_invalid_citation_abstains_and_errors_stay_errors(self):
        class Engine:
            def search(self, *args):
                return [chunk("id", "supported fact")]
        class Controller:
            def decide(self, question, context=None, aliases=None):
                return ({"action": "search", "query": question} if context is None else
                        {"action": "answer", "answer": "A claim [C99]", "citations": ["C99"]}), {"event": "model"}
        result = run_agent("question", {}, self.config, Engine(), Controller())
        self.assertEqual(result["status"], "abstain")
        class Broken:
            def search(self, *args):
                raise ConnectionError("real failure")
        result = run_agent("question", {}, self.config, Broken(), Controller())
        self.assertEqual(result["status"], "error")
        self.assertIn("real failure", result["error"])

    def test_controller_sees_question_and_context_without_gold(self):
        observed = []
        class Engine:
            def search(self, *args):
                return [chunk("id", "supported fact")]
        class Controller:
            def decide(self, question, context=None, aliases=None):
                observed.append((question, context))
                return ({"action": "search", "query": question} if context is None else
                        {"action": "answer", "answer": "supported fact [C1]", "citations": ["C1"]}), {"event": "model"}
        result = run_agent("question", {}, self.config, Engine(), Controller())
        self.assertEqual(result["status"], "answered")
        self.assertEqual(result["citations"], ["id"])
        self.assertIn("[id]", result["answer"])
        self.assertEqual(len(observed), 2)


class FrozenBenchmarkTests(unittest.TestCase):
    def test_counts_hashes_and_source_evidence(self):
        cases = load(ROOT / "benchmark/cases.json")
        self.assertEqual(len({q["id"] for q in cases}), len(cases))
        for split, yes, no in (("dev", 15, 2), ("test", 5, 2)):
            self.assertGreaterEqual(sum(q["split"] == split and q["answerable"] for q in cases), yes)
            self.assertGreaterEqual(sum(q["split"] == split and not q["answerable"] for q in cases), no)
        pages = [json.loads(line) for line in (ROOT / "data/day6/pages.jsonl").read_text(encoding="utf-8").splitlines()]
        for q in cases:
            for gold in q["gold"]:
                self.assertTrue(any(p["page"] == gold["page"] and p["document_id"] == gold["source_id"]
                                    and gold["evidence"] in p["text"] for p in pages), q["id"])
        for relative, sha in load(ROOT / "benchmark/frozen_inputs.json")["sha256"].items():
            self.assertEqual(digest(ROOT / relative), sha)


if __name__ == "__main__":
    unittest.main()
