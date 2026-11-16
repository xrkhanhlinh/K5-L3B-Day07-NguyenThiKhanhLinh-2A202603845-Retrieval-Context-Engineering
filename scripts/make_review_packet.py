"""Readable source, answer and citation packet; does not invent review labels."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import ROOT, load


if __name__ == "__main__":
    cases = {q["id"]: q for q in load(ROOT / "benchmark/cases.json")}
    lines = ["# Gói đọc kiểm chứng Day 7", "", "Nhãn do Codex AI đọc và ghi; học viên/người chấm độc lập chưa xác nhận. Không dùng gói này làm input cho agent.", ""]
    for path in sorted((ROOT / "results").glob("*/*/agent.json")):
        review_path = path.parent / "reviews.json"
        reviews = {r["query_id"]: r for r in load(review_path)} if review_path.exists() else {}
        split, name = path.parent.parent.name, path.parent.name
        for trace in load(path):
            case = cases[trace["query_id"]]
            lines += [f"## {split}/{name}/{case['id']}", "", f"**Câu hỏi:** {case['question']}", "",
                      f"**Kỳ vọng:** {case.get('expected_answer', 'Tìm và từ chối vì thiếu bằng chứng.')}", "",
                      f"**Gold evidence (chỉ dùng đánh giá):** {case.get('gold', [])}", "",
                      f"**Trạng thái:** {trace['status']}", "", f"**Câu trả lời:** {trace['answer']}", "",
                      f"**Nhãn:** {reviews.get(case['id'], 'CHƯA CHẤM')}", "", "### Context thật gửi model", ""]
            for row in trace["context_rows"]:
                meta = row["metadata"]
                lines += [f"**{row['alias']} · ID `{row['id']}` · đơn vị {row['page']} · chương {meta.get('chapter')} · offsets {meta.get('start')}–{meta.get('end')}**", "",
                          f"Nguồn: {row['source']}", "", "> " + row["text"].replace("\n", "\n> "), ""]
    (ROOT / "results/REVIEW_PACKET.md").write_text("\n".join(lines), encoding="utf-8")
    print("Generated source/answer review packet")
