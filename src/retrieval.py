"""Dense Day 6 Qdrant, BM25 and reciprocal-rank fusion, without benchmark labels."""
import math
import re
import time
import unicodedata
from collections import Counter

from .common import ROOT, digest, load


def tokens(text):
    return re.findall(r"[^\W_]+", unicodedata.normalize("NFC", text).casefold())


def matches(chunk, filters):
    for key, value in (filters or {}).items():
        if key not in {"chapter", "language", "document_id", "page"} or type(value) not in (str, int, bool):
            raise ValueError(f"Unsupported metadata filter: {key}")
        actual = chunk.get("page") if key == "page" else chunk.get("source_id") if key == "document_id" else chunk["metadata"].get(key)
        if actual != value:
            return False
    return True


class BM25:
    def __init__(self, chunks, k1=1.5, b=0.75):
        self.chunks, self.k1, self.b = chunks, k1, b
        self.counts = [Counter(tokens(c["text"])) for c in chunks]
        self.lengths = [sum(row.values()) for row in self.counts]
        self.avg = sum(self.lengths) / len(chunks)
        df = Counter(term for row in self.counts for term in row)
        self.idf = {term: math.log(1 + (len(chunks) - n + 0.5) / (n + 0.5)) for term, n in df.items()}

    def search(self, query, filters=None, top_k=3):
        terms = set(tokens(query))
        out = []
        for chunk, counts, length in zip(self.chunks, self.counts, self.lengths):
            if not matches(chunk, filters):
                continue
            norm = self.k1 * (1 - self.b + self.b * length / self.avg)
            score = sum(self.idf.get(t, 0) * counts[t] * (self.k1 + 1) / (counts[t] + norm) for t in terms if counts[t])
            if score > 0:
                out.append({**chunk, "score": score, "method": "bm25"})
        return sorted(out, key=lambda c: (-c["score"], c["id"]))[:top_k]


def fuse(dense, lexical, top_k, k=60):
    found, scores, ranks = {}, Counter(), {}
    for label, rows in (("dense", dense), ("bm25", lexical)):
        for rank, chunk in enumerate(rows, 1):
            cid = chunk["id"]
            found[cid] = chunk
            scores[cid] += 1 / (k + rank)
            ranks.setdefault(cid, {})[label] = {"rank": rank, "score": chunk["score"]}
    return [{**found[cid], "score": scores[cid], "method": "hybrid", "component_ranks": ranks[cid]}
            for cid in sorted(found, key=lambda cid: (-scores[cid], cid))[:top_k]]


class RetrievalEngine:
    def __init__(self):
        # Imports stay lazy so lexical/unit checks need no model download.
        from qdrant_client import QdrantClient
        self.chunks = load(ROOT / "data/day6/chunks.json")
        self.by_id = {c["id"]: c for c in self.chunks}
        self.lexical = BM25(self.chunks)
        original = load(ROOT / "data/day6/run_info.json")
        weight = next((p for p in (ROOT / ".model_cache").rglob("model.onnx")
                       if digest(p) == next(v for k, v in original["model_files"].items() if k.endswith("model.onnx"))), None)
        if weight is None:
            raise RuntimeError("Exact Day 6 encoder not cached; run scripts/cache_embedding.py")
        self.embedding_path = weight.parent
        self.encoder_sha256 = digest(weight)
        self.embedder = None
        self.client = QdrantClient(path=str(ROOT / ".qdrant"))
        self.query_cache = {}
        for path in (ROOT / "artifacts").glob("query_vectors_*.json"):
            cached = load(path)
            if cached["encoder_sha256"] != self.encoder_sha256:
                raise RuntimeError("Query vector cache uses a different encoder")
            self.query_cache.update({q["question"]: q["vector"] for q in cached["queries"]})
        info = self.client.get_collection("day06_C")
        if info.points_count != len(self.chunks) or info.config.params.vectors.size != 384:
            raise RuntimeError("Day 6 index dimension/count mismatch")
        points, offset = self.client.scroll("day06_C", limit=1000, with_payload=True, with_vectors=False)
        if offset is not None or {p.payload["chunk_id"] for p in points} != set(self.by_id):
            raise RuntimeError("Day 6 index IDs differ from frozen chunk export")
        for point in points:
            c = self.by_id[point.payload["chunk_id"]]
            if point.payload["text"] != c["text"] or point.payload["page"] != c["page"] or point.payload["source"] != c["source"]:
                raise RuntimeError("Day 6 payload mismatch")

    def dense(self, query, filters, top_k):
        from qdrant_client import models
        if query not in self.query_cache:
            if self.embedder is None:
                from fastembed import TextEmbedding
                self.embedder = TextEmbedding("sentence-transformers/all-MiniLM-L6-v2", cache_dir=str(ROOT / ".model_cache"),
                    threads=4, providers=["CPUExecutionProvider"], local_files_only=True,
                    specific_model_path=str(self.embedding_path))
            vector = list(self.embedder.embed([query]))[0].tolist()
            if len(vector) != 384 or not all(math.isfinite(v) for v in vector):
                raise ValueError("Invalid real query embedding")
            self.query_cache[query] = vector
        conditions = []
        # Validate filters even when an empty result would otherwise mask a bad key.
        matches(self.chunks[0], filters)
        for key, value in (filters or {}).items():
            conditions.append(models.FieldCondition(key=key, match=models.MatchValue(value=value)))
        result = self.client.query_points("day06_C", query=self.query_cache[query], limit=top_k,
            query_filter=models.Filter(must=conditions) if conditions else None,
            with_payload=True)
        return [{**self.by_id[p.payload["chunk_id"]], "score": float(p.score), "method": "dense"} for p in result.points]

    def search(self, query, method, filters=None, top_k=3):
        if not isinstance(query, str) or not query.strip() or top_k < 1:
            raise ValueError("Nonempty query and positive top_k required")
        if method == "dense":
            rows = self.dense(query, filters, top_k)
        elif method == "bm25":
            rows = self.lexical.search(query, filters, top_k)
        elif method == "hybrid":
            rows = fuse(self.dense(query, filters, 20), self.lexical.search(query, filters, 20), top_k)
        else:
            raise ValueError(f"Unknown method {method}")
        return [{**row, "rank": rank} for rank, row in enumerate(rows, 1)]

    def close(self):
        self.client.close()


def pack_context(results, budget):
    selected, seen, blocks = [], set(), []
    for row in results:
        if row["id"] in seen:
            continue
        seen.add(row["id"])
        alias = f"C{len(selected) + 1}"
        block = f"[{alias}] source={row['source']} unit={row['page']} chapter={row['metadata'].get('chapter')}\n{row['text']}"
        if len("\n\n".join(blocks + [block])) <= budget:
            selected.append({**row, "alias": alias})
            blocks.append(block)
    return "\n\n".join(blocks), selected
