# Code

Agent kết nối model Qwen2.5 qua llama.cpp local và vector store Qdrant Day 6.

- `agent.py`: điều phối model, gọi retrieval, đóng gói context và citation.
- `retrieval.py`: dense, BM25 và hybrid RRF.
- `evaluate.py`: tổng hợp retrieval metrics và nhãn đánh giá agent.
- `ask.py`: CLI hỏi đáp, chạy bằng `python -m src.ask "câu hỏi"`.
- `common.py`: đọc/ghi JSON và kiểm tra hash.

Xem [báo cáo cá nhân](../report/individual/2A202603845_NguyenThiKhanhLinh.md) để cài đặt, chạy model và tái lập benchmark.
