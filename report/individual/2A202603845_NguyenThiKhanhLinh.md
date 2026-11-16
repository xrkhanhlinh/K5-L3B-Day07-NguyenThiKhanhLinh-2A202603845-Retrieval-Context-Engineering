# Báo cáo cá nhân — Day 7: Agentic RAG

**Nguyễn Thị Khánh Linh · MSSV 2A202603845 · Lớp L3B**

Ngày thực hiện: **16/11/2026 (UTC+7)**. Phạm vi: phần cơ bản tối đa 85 điểm. Không thực hiện thử thách nâng cao tùy chọn 15 điểm.

## Dữ liệu và benchmark

Dùng lại corpus *Alice’s Adventures in Wonderland* bản tiếng Anh Project Gutenberg eBook #11 của Day 6: **52 đơn vị nội dung, 142.880 ký tự**. Đây là các nhóm đoạn tuần tự của văn bản, **không phải 52 trang PDF vật lý**. Quy tắc chia đơn vị, nguồn, snapshot và quyền sử dụng được giữ ở [manifest](../../data/day6/manifest.json); văn bản và credit/giấy phép gốc ở [pg11.txt](../../data/day6/pg11.txt). Corpus đã dùng ở Day 6, không tự tạo corpus mới hay nhân bản để đạt số trang.

Nguồn là bản tiếng Anh gốc, được manifest Day 6 ghi public domain tại Hoa Kỳ; không dùng bản dịch hiện đại, hình minh họa hoặc dữ liệu cá nhân. Giữ nguyên thông tin giấy phép và đường dẫn nguồn; quyền sử dụng tại nơi khai thác cần được người dùng kiểm tra. Người chấm có snapshot trong repo để đối chiếu.

Dùng **204 chunk của cấu hình C Day 6**, giữ nguyên ID/text/source/page/chapter/offset. Copy database Qdrant sang `.qdrant/` Day 7, collection **`day06_C`**, không thay đổi database Day 6. Khi mở, code xác minh số điểm, chiều vector, toàn bộ ID, text, nguồn và đơn vị so với export. Truy xuất local exact cosine. Nếu không có database local, [script tái tạo](../../scripts/rebuild_index.py) tạo lại index từ [vector thật đã xuất từ Day 6](../../data/day6/vectors.json), giữ cùng encoder và ghi chi phí thời gian; không dùng vector giả. Đã kiểm tra tái tạo ở thư mục index riêng.

Embedding: **`sentence-transformers/all-MiniLM-L6-v2`**, 384 chiều, FastEmbed/ONNX CPU; query và document cùng encoder, không prefix. Giữ model cache Day 6, dùng `local_files_only=True` khi benchmark. Để giảm RAM đỉnh, query gốc được embedding thật trong tiến trình riêng: [17 query dev](../../artifacts/query_vectors_dev.json), rồi [7 query test](../../artifacts/query_vectors_test.json) chỉ sau khi đã chốt cấu hình. Agent tải vector query cache, không giữ ONNX và LLM đồng thời; gold/đáp án không đi vào encoder. Hash encoder và toàn bộ vector được lưu để kiểm tra. Thông tin phiên bản/hash encoder gốc ở [run_info Day 6](../../data/day6/run_info.json); package Day 7 ở [run_info](../../results/run_info.json).

Agent: **Qwen2.5-0.5B-Instruct, GGUF Q4_K_M**, revision `9217f5db79a29953eb74d5343926648285ec7e67`, chạy CPU qua **llama.cpp b12430**. Model SHA-256 `74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db`. Server chỉ lắng nghe `127.0.0.1:8087`, 4 thread, context 4096 token, một slot; temperature 0, seed 7. [Manifest model/runtime](../../artifacts/local_model.json) lưu URL chính thức, hash và kích thước tải. Không gọi API model bên ngoài, không cần API key.

| Split | Có đáp án | Thiếu evidence | Tổng |
|---|---:|---:|---:|
| Dev | 15 | 2 | 17 |
| Test | 5 | 2 | 7 |
| **Tổng** | **20** | **4** | **24** |

[Benchmark](../../benchmark/cases.json) giữ 15 câu dev Day 6 và thêm 2 câu thiếu evidence. **Không dùng lại 5 câu test Day 6**: 5 câu test có đáp án Day 7 hỏi các sự kiện khác, thêm 2 câu thiếu evidence. Chia trước khi chạy. Bộ test mới do cùng công cụ hỗ trợ tạo, cùng sách và nhân vật nên chỉ là held-out theo câu hỏi, không phải benchmark bên ngoài hay holdout theo tài liệu.

Câu có đáp án có nguồn, đơn vị và quote; evidence thay thế được hiểu là OR, không có câu multi-hop bắt buộc nhiều evidence. Câu thiếu evidence hỏi dữ kiện gần chủ đề nhưng văn bản không nêu: lương Rabbit, ngày sinh Cheshire Cat, điện thoại Queen và địa chỉ Mock Turtle. [Audit thiếu evidence](../../benchmark/absence_audit.json) ghi scan toàn 52 đơn vị, các từ khóa/đoạn khớp và vùng nội dung nhân vật được kiểm tra; không suy từ việc top-k không tìm thấy.

Trong kiểm tra dev ban đầu, phát hiện evidence tương đương cho d10 (Pigeon, đơn vị 20) và d11 (pig, đơn vị 25). Bổ sung nhãn dev, ghi [lịch sử đóng băng](../../benchmark/frozen_inputs.json) và giữ [hash trước sửa](../../benchmark/frozen_inputs_preliminary.json), rồi chạy lại toàn bộ retrieval dev trên cùng nhãn. Các file `retrieval_preliminary.json` chỉ là minh chứng trước sửa nhãn, không dùng làm kết quả cuối. Không thay câu hỏi, split, đáp án hay gold test để tăng điểm.

Đã thử model 1.5B trước lượt chính, nhưng máy 7,77 GiB RAM ở mức tải 93%, còn 0,50 GiB; một request chẩn đoán mất 979,56 giây. [Ghi nhận tài nguyên](../../artifacts/resource_observation.json), [manifest model pilot](../../artifacts/pilot_1_5b_model.json), các `prompt_pilot*_traces.json` và `prompt_diagnostics.json` trong artifacts giữ kết quả thử, không trộn với bảng so sánh cuối. Chuyển sang 0.5B và tách bước embedding giúp giảm RAM; không đóng ứng dụng khác của người dùng. Các pilot từ chối nhầm hoặc lặp placeholder được dùng để sửa prompt trên dev, trước test.

**Người/công cụ chấm: Codex AI đọc câu trả lời, đoạn citation và nguồn gốc. Chưa có học viên/người chấm độc lập xác nhận nhãn.** Các tỷ lệ ngữ nghĩa dưới đây là nhãn AI có lý do và bằng chứng để học viên rà soát; không trình bày thành audit thủ công đã được học viên thực hiện.

## Retrieval và thử nghiệm

Ba phương pháp khác nhau: **dense**, **BM25** và **hybrid RRF**. BM25: k1=1,5; b=0,75; token Unicode chữ/số, lowercase, không stemming. Hybrid lấy 20 candidate từ mỗi retriever, hợp nhất theo `sum(1/(60+rank))`, trọng số 1:1, dedup ID; không cộng raw cosine với raw BM25. Tất cả dùng cùng 204 chunk, câu hỏi và nhãn. Filter `chapter` chỉ lấy từ phạm vi có sẵn trong câu hỏi, áp dụng nhất quán; không suy filter từ gold.

| Cấu hình | Phương pháp, top-k, context budget | Giả thuyết / thay đổi |
|---|---|---|
| dense | dense, k=3, 3200 ký tự gồm nguồn | Baseline: reuse Day 6 dense C and explicit chapter filters. |
| bm25 | bm25, k=3, 3200 ký tự gồm nguồn | Improvement 1: lexical matching recovers rare names and exact phrases missed by dense. |
| hybrid | hybrid, k=3, 3200 ký tự gồm nguồn | Improvement 2: RRF of dense and BM25 combines semantic and lexical evidence. |
| hybrid_context | hybrid, k=6, 6200 ký tự gồm nguồn | Improvement 3: a larger deduplicated context may retain evidence below rank 3, with increased model cost. |
| hybrid_plain | hybrid, k=3, 3200 ký tự gồm nguồn | Dev JSON refusals and copied placeholders suggest format burden on a 0.5B model. Test natural-language generation, then BM25 attribution from question + generated draft over actual context. Citation semantic support still reviewed manually; no gold used. |

BM25 và hybrid đồng thời là hai cấu hình thử cải thiện baseline; không khẳng định mọi thử nghiệm đều tăng điểm. `hybrid_context` tăng context mà giữ ranking hybrid. Sau khi thấy lỗi format/abstention trên dev, công bố thêm `hybrid_plain` trước khi chạy cấu hình đó: giữ retrieval hybrid k=3, cho model sinh câu tự nhiên; khi model không tự ghi nhãn nguồn, app chọn một citation bằng BM25 trên `question + draft` trong context thật. Đây là thử nghiệm generation/citation, không phải phương pháp retrieval thứ tư. Ghi sửa protocol trong lịch sử đóng băng; không thay câu hỏi/gold test. Không rerank retrieval hay query rewrite/multi-hop. Mỗi câu tối đa một search.

Hit@1/Hit@3: một chunk đúng nguồn và đơn vị chứa trọn ít nhất một gold quote; cutoff top-3 cố định kể cả cấu hình k=6. Context Evidence Rate là số câu có đủ gold evidence trong **context cuối thực sự gửi model**, chia số câu có đáp án; câu thiếu evidence không vào mẫu số. Chấm ngữ nghĩa context 0/1/2 được lưu riêng. Exact-quote proxy vẫn có thể bỏ sót evidence tương đương chưa được gán nhãn.

| Cấu hình | Split | Hit@1 | Evidence Hit@3 | Context Evidence Rate (agent) | Agent giây / phí API |
|---|---|---|---|---|---|
| dense | dev | 7/15 (46.7%) | 11/15 (73.3%) | 11/15 (73.3%) | 76.40 s / 0 USD |
| bm25 | dev | 7/15 (46.7%) | 11/15 (73.3%) | 11/15 (73.3%) | 138.16 s / 0 USD |
| hybrid | dev | 6/15 (40.0%) | 12/15 (80.0%) | 12/15 (80.0%) | 111.94 s / 0 USD |
| hybrid_context | dev | 6/15 (40.0%) | 12/15 (80.0%) | 12/15 (80.0%) | 149.05 s / 0 USD |
| hybrid_plain | dev | 6/15 (40.0%) | 12/15 (80.0%) | 12/15 (80.0%) | 113.92 s / 0 USD |
| dense | test | 2/5 (40.0%) | 4/5 (80.0%) | 4/5 (80.0%) | 42.90 s / 0 USD |
| hybrid_plain | test | 2/5 (40.0%) | 4/5 (80.0%) | 4/5 (80.0%) | 37.72 s / 0 USD |

**Chọn `hybrid_plain` trên dev**, theo tiêu chí công bố trong [protocol](../../benchmark/protocol.json): ưu tiên trung bình grounded answer, rồi Context Evidence Rate, rồi Evidence Hit@3, rồi tổng thời gian agent thấp hơn, rồi tên cấu hình. [selection.json](../../results/selection.json) lưu quyết định lúc `2026-11-16T10:03:23.965896+00:00`, toàn bộ kết quả dev và hash implementation, trước test. Baseline dense và cấu hình chọn được chạy trên cùng 7 câu test sau khi chốt; không sửa pipeline theo test.

| Cấu hình | Split | Retrieval median ms | Context trung bình (ký tự) | Prompt token | Completion token |
|---|---|---:|---:|---:|---:|
| dense | dev | 33.844 | 2317.9 | 13689 | 946 |
| bm25 | dev | 3.231 | 2407.8 | 14227 | 986 |
| hybrid | dev | 8.248 | 2354.1 | 13908 | 932 |
| hybrid_context | dev | 7.892 | 4825.9 | 24338 | 1020 |
| hybrid_plain | dev | 6.504 | 2354.1 | 13041 | 656 |
| dense | test | 2.266 | 2351.3 | 5703 | 420 |
| hybrid_plain | test | 7.200 | 2467.3 | 5536 | 287 |

Phí dịch vụ API là **0 USD** vì chạy local; không tính điện, phần cứng, mạng, tải/cài model. Thời gian agent gồm quyết định model, search, context, generation và attribution nếu có; không gồm tải/khởi động model và preprocessing query. Thời gian preprocessing thật được lưu ở hai file query_vectors. Các lượt retrieval dev gốc có query embedding cache theo tiến trình; lượt hybrid_plain/test dùng cache tiền xử lý. Do khác cache, thứ tự và tải máy, chỉ dùng thời gian như quan sát của lần chạy, không tuyên bố một retriever nhanh hơn tổng quát. Thời gian pilot được lưu riêng, không giấu vào số của cấu hình khác.

### Phân tích lỗi dev và kết quả trước/sau

- **d08 — What happened to the pebbles thrown into the Rabbit's house?**
  - dense: context_hit=False, grounded=0/2, answered; Bịa pebbles bị nghiền do mở cửa. Context không có biến đổi thành cakes; citation C1 đơn vị 52 chỉ kể lại giấc mơ, không hỗ trợ khẳng định.
  - bm25: context_hit=True, grounded=0/2, abstain; Từ chối nhầm dù BM25 tìm được đoạn pebbles turning into little cakes ở đơn vị 15.
  - hybrid: context_hit=False, grounded=0/2, answered; Bịa soldiers lấy pebbles và ghép cảnh croquet vào nhà Rabbit. C1 chỉ là yêu cầu mang gloves/fan; không hỗ trợ biến đổi của pebbles.
  - hybrid_context: context_hit=False, grounded=0/2, answered; Ghép sai cảnh soldiers, đổi Dinah thành Duchess và bịa số phận pebbles. C1/C2/C4/C5/C6 không có biến đổi pebbles; C3 có đe dọa đốt nhà nhưng người nói và Dinah khác đáp án. Không citation nào hỗ trợ đầy đủ khẳng định.
  - hybrid_plain: context_hit=False, grounded=0/2, answered; Bịa soldiers lấy pebbles. Citation C2 đơn vị 33 là cảnh croquet, không phải pebbles biến thành cakes ở nhà Rabbit.
- **d13 — According to the Hatter, what time is it always now?**
  - dense: context_hit=False, grounded=0/2, answered; Trả lời half-past one sai với always six o'clock. Context có ví dụ giả định thời gian và chiếc đồng hồ, thiếu phát biểu always six; các citation C2/C3 không hỗ trợ đáp án.
  - bm25: context_hit=True, grounded=0/2, abstain; Từ chối nhầm dù context có lời Hatter It's always six o'clock now.
  - hybrid: context_hit=True, grounded=0/2, answered; Trả lời half-past one sai điều kiện always now. C2 ghi always six; C3 chỉ ví dụ giả định giờ ăn trưa, không hỗ trợ khẳng định thời gian luôn là half-past one.
  - hybrid_context: context_hit=True, grounded=0/2, abstain; Từ chối nhầm dù context có always six o'clock now.
  - hybrid_plain: context_hit=True, grounded=2/2, answered; Đáp án always 6 o'clock đúng và C2 context có always six. Citation tự động lại chọn C1 đơn vị 27 về watch/year, không có always six. Vì vậy grounded answer theo toàn context là 2 nhưng citation này không hợp lệ về ngữ nghĩa.
- **d04 — What did Alice use that caused her to shrink again in the pool-of-tears episode?**
  - dense: context_hit=False, grounded=0/2, abstain; Context nói về nước mắt, bơi trong hồ và khóc; không có đoạn chiếc quạt gây thu nhỏ. Từ chối có cơ sở theo context nhưng câu có đáp án nên chấm 0.
  - bm25: context_hit=False, grounded=0/2, abstain; Không truy ra đoạn fan gây thu nhỏ; context về khóc và em bé không đủ trả lời.
  - hybrid: context_hit=False, grounded=0/2, abstain; Context chưa có chiếc quạt gây thu nhỏ; câu có đáp án bị từ chối chấm 0.
  - hybrid_context: context_hit=False, grounded=0/2, abstain; Context lớn vẫn không có fan gây thu nhỏ, chỉ các đoạn liên quan nước mắt và kích thước khác.
  - hybrid_plain: context_hit=False, grounded=0/2, answered; Bịa Alice dùng foot để thu nhỏ. C2 chỉ nói foot slipped vào nước, không có nguyên nhân fan và không hỗ trợ đáp án.
- **d06 — What prize did the Dodo present to Alice?**
  - dense: context_hit=False, grounded=0/2, answered; Trả lời box of comfits nhầm giải Alice phát cho các con vật với giải Dodo trao Alice. Context chỉ đến Hand it over here, thiếu đoạn trao lại thimble.
  - bm25: context_hit=False, grounded=1/2, answered; Đúng tên vật thimble nhưng context dừng ở Dodo yêu cầu Alice đưa thimble, thiếu đoạn Dodo trao lại và điều kiện her own. Chấm đúng một phần, không nhận citation là hỗ trợ đầy đủ.
  - hybrid: context_hit=False, grounded=0/2, answered; Nhầm comfits Alice phát cho các con vật với thimble Dodo trao Alice. C1 chỉ có phát comfits và Dodo yêu cầu đưa thimble, không hỗ trợ đáp án sai.
  - hybrid_context: context_hit=False, grounded=1/2, answered; Đúng vật thimble nhưng thiếu her own và chứng cứ Dodo trao lại; C1 kết thúc ở Hand it over here nên chỉ hỗ trợ một phần tình tiết.
  - hybrid_plain: context_hit=False, grounded=0/2, answered; Dodo trao box of comfits là sai; C1 nói Alice phát comfits và Dodo lấy thimble, chưa có đoạn trao lại thimble.

d08 kiểm tra giả thuyết từ khóa `pebbles`: BM25 có thể lấy đúng sự kiện mà dense bỏ sót, còn RRF có thể đẩy chunk lexical xuống dưới cutoff. d13 kiểm tra chi tiết `six o’clock`: truy xuất cùng chủ đề Hatter chưa đủ tìm đúng thời điểm. d04 là thiếu bằng chứng fan trong context; tăng budget không giúp nếu candidate vẫn không có đoạn cần thiết. d06 có chunk kết thúc ở lời Dodo yêu cầu đưa thimble, thiếu đoạn trao lại; đây là giới hạn chunk/đoạn lân cận, không phải lỗi giải quyết chỉ bằng số chunk. Các kết quả trên là quan sát dev, không dùng lỗi test để đổi cấu hình.

## Agent và đánh giá

[Agent](../../src/agent.py) dùng model thật qua HTTP local: bước đầu model chọn `search` hoặc `abstain` bằng action JSON có schema; nếu search, query bị ràng buộc là câu hỏi gốc. App thực thi tool, dedup và đóng gói nguyên chunk theo thứ hạng vào budget tính bằng ký tự gồm nguồn. Bốn cấu hình đầu yêu cầu model trả answer/citations dạng JSON; `hybrid_plain` sinh câu tự nhiên rồi attribution như mô tả trên. App chuẩn hóa thiếu citation hoặc câu nêu rõ không có thông tin thành abstain. Đây là giao thức tool JSON do ứng dụng thực thi, không phải native function-calling hay planner nhiều bước.

Context dùng alias C1/C2; app ánh xạ citation về ID chunk Day 6 đầy đủ và tự thêm inline citation khi cần. Citation ID lạ/không có trong context làm kết quả chuyển thành abstain; giữ raw output và sự kiện normalization/attribution để kiểm tra. Kiểm tra ID và BM25 attribution **không chứng minh nguồn hỗ trợ nội dung**: d13 dev và t02 test là ví dụ trả lời đúng nhưng gắn nhầm đoạn. Chấm citation riêng bằng đọc nguồn. Không đưa gold/nhãn/đáp án chuẩn vào model/tool. System prompt coi nguồn là dữ liệu, không phải chỉ dẫn. Chưa kiểm thử đầy đủ prompt injection.

Giới hạn một search/câu để kiểm soát thời gian/chi phí và giữ so sánh đơn giản; không coi đây là giới hạn bắt buộc của đề. Dừng sau trả lời/từ chối. HTTP timeout 180 s; lỗi HTTP, model JSON hoặc store được lưu `status=error`, không trả kết quả giả. Lỗi được báo riêng, không lẫn với abstention đúng.

| Cấu hình / split | Tool use | Lượt search | Grounded 0/1/2; trung bình /2 | Citation hợp lệ | Câu trả lời có citation | Abstention đúng | Từ chối nhầm | Lỗi |
|---|---|---|---|---|---|---|---|---:|
| dense/dev | 17/17 (100.0%) | {'1': 17} | 12/0/3; 0.400 | 4/13 (30.8%) | 8/8 (100.0%) | 2/2 (100.0%) | 7/15 (46.7%) | 0 |
| bm25/dev | 17/17 (100.0%) | {'1': 17} | 13/2/0; 0.133 | 0/6 (0.0%) | 3/3 (100.0%) | 2/2 (100.0%) | 12/15 (80.0%) | 0 |
| hybrid/dev | 17/17 (100.0%) | {'1': 17} | 12/0/3; 0.400 | 3/9 (33.3%) | 8/8 (100.0%) | 1/2 (50.0%) | 8/15 (53.3%) | 0 |
| hybrid_context/dev | 17/17 (100.0%) | {'1': 17} | 12/1/2; 0.333 | 2/23 (8.7%) | 9/9 (100.0%) | 1/2 (50.0%) | 7/15 (46.7%) | 0 |
| hybrid_plain/dev | 17/17 (100.0%) | {'1': 17} | 9/1/5; 0.733 | 5/16 (31.2%) | 16/16 (100.0%) | 1/2 (50.0%) | 0/15 (0.0%) | 0 |
| dense/test | 7/7 (100.0%) | {'1': 7} | 4/0/1; 0.400 | 1/7 (14.3%) | 3/3 (100.0%) | 2/2 (100.0%) | 2/5 (40.0%) | 0 |
| hybrid_plain/test | 7/7 (100.0%) | {'1': 7} | 3/0/2; 0.800 | 1/6 (16.7%) | 6/6 (100.0%) | 1/2 (50.0%) | 0/5 (0.0%) | 0 |

Grounded answer: 0 sai/thiếu evidence hoặc từ chối câu có đáp án; 1 đúng một phần; 2 đúng và đủ theo toàn context. Citation được chấm riêng: chỉ đạt nếu đoạn được trỏ tới thực sự hỗ trợ nội dung/điều kiện. Vì vậy một đáp án đúng nhưng gắn nhầm đoạn có thể answer=2 và citation=false; một phát biểu về nhãn lọ được nguồn hỗ trợ vẫn có thể answer=0 vì không trả lời lọ chứa gì. Không đánh đồng citation hợp lệ với trả lời đúng câu hỏi. Câu thiếu evidence được đọc để xác nhận từ chối không thêm khẳng định vô căn cứ. Từng citation có nhãn boolean, quote/đơn vị và lý do trong reviews.json.

### Chấm context toàn bộ 5 câu test có đáp án

| Cấu hình | Context 0 | Context 1 | Context 2 |
|---|---:|---:|---:|
| dense | 1 | 0 | 4 |
| hybrid_plain | 1 | 0 | 4 |

0 = không có bằng chứng trả lời; 1 = có phần liên quan nhưng thiếu điều kiện/nguồn; 2 = đủ bằng chứng và nguồn. Bảng từng câu bên dưới kèm lý do; đã giữ nguyên cả lỗi và từ chối nhầm.

### Toàn bộ câu trả lời test và lý do chấm

| Cấu hình / Query | Loại câu, tool / nguồn context | Câu trả lời và citation | Nhãn và lý do |
|---|---|---|---|
| dense/t01 | Có đáp án; dense; C1=unit38, C2=unit38, C3=unit39 | The Queen orders Alice to see the Mock Turtle. [C1:unit38] | context 2; answer 0; Không trả lời người được Queen sai dẫn Alice là Gryphon, mà nói Queen orders Alice. C1 đơn vị 38 ghi Queen nói với Gryphon take this young lady; không hỗ trợ sai người nhận mệnh lệnh. |
| dense/t02 | Có đáp án; dense; C1=unit41, C2=unit41, C3=unit41 | 2 [C1:unit41] [C2:unit41] [C3:unit41] | context 2; answer 2; Đáp án 2 đúng; C2 ghi Two lines. C1 chỉ lời bài hát, C3 mới nói a line trước khi được sửa thành two, nên hai citation đó chưa hỗ trợ số lượng 2. |
| dense/t03 | Có đáp án; dense; C1=unit45, C2=unit45, C3=unit50 | Not enough evidence in the provided documents. | context 2; answer 0; Từ chối nhầm: C1 đơn vị 45 nói ghi tên vì sợ quên trước khi hết phiên tòa. |
| dense/t04 | Có đáp án; dense; C1=unit50, C2=unit49, C3=unit49 | Not enough evidence in the provided documents. | context 2; answer 0; Từ chối nhầm: C2 đơn vị 49 ghi Rule Forty-two và more than a mile high rõ ràng. |
| dense/t05 | Có đáp án; dense; C1=unit52, C2=unit52, C3=unit46 | Alice's head is resting on her hand when she wakes from the dream. [C1:unit52] [C2:unit52] [C3:unit46] | context 0; answer 0; Nhầm Alice với người chị leaning her head on her hand sau khi Alice rời đi. C1 chỉ là chị tưởng tượng bàn tay Alice trên đầu gối; C2 là đầu người chị; C3 là Alice lớn lên tại tòa. Không đoạn nào nêu đầu Alice trong lòng chị lúc tỉnh giấc. |
| dense/t06 | Thiếu evidence; dense; C1=unit31, C2=unit45, C3=unit32 | Not enough evidence in the provided documents. | abstention=True; Đầu ra cuối chỉ nêu thiếu bằng chứng, không bịa số điện thoại Queen; audit corpus không có dữ kiện điện thoại. |
| dense/t07 | Thiếu evidence; dense; C1=unit42, C2=unit39, C3=unit41 | Not enough evidence in the provided documents. | abstention=True; Từ chối đúng, không suy địa chỉ từ nguồn/trang; các đoạn Mock Turtle về lịch sử và dance không có địa chỉ nhà. |
| hybrid_plain/t01 | Có đáp án; hybrid; C1=unit38, C2=unit39, C3=unit38 | The Queen orders the Mock Turtle to take Alice to see him. [C1:unit38] | context 2; answer 0; Trả lời Queen sai Mock Turtle dẫn Alice tới chính mình, sai người nhận mệnh lệnh. C1 ghi người đó là Gryphon, nên citation không hỗ trợ đáp án. |
| hybrid_plain/t02 | Có đáp án; hybrid; C1=unit41, C2=unit41, C3=unit43 | The Lobster Quadrille starts with two lines. [C1:unit41] | context 2; answer 2; Nội dung two lines đúng, C2 trong context chứng minh. Citation tự động lại chọn C1 chỉ có a line và chưa có lời sửa Two lines; grounded answer theo toàn context là 2 nhưng citation sai về điều kiện số lượng. |
| hybrid_plain/t03 | Có đáp án; hybrid; C1=unit45, C2=unit49, C3=unit46 | The jurors write down their names before the trial begins because they can't have anything to put down yet, before the end of the trial. [C1:unit45] | context 2; answer 0; Nhầm câu hỏi/nhận xét của Alice với lý do Gryphon nêu. Đáp án không nói fear they should forget their names mà ghép can't have anything to put down với before end of trial. C1 chứa đáp án chuẩn nhưng không hỗ trợ quan hệ nguyên nhân sai này. |
| hybrid_plain/t04 | Có đáp án; hybrid; C1=unit50, C2=unit49, C3=unit51 | Rule Forty-two requires a person to leave the court if they are more than a mile high. [C2:unit49] | context 2; answer 2; Đúng điều kiện more than a mile high và hành vi leave the court; citation C2 đơn vị 49 xác định đúng Rule Forty-two. |
| hybrid_plain/t05 | Có đáp án; hybrid; C1=unit52, C2=unit52, C3=unit19 | Alice's head is free when she wakes from the dream. [C3:unit19] | context 0; answer 0; Nói head is free sai sự kiện tỉnh giấc. C3 đơn vị 19 là cảnh Alice dài cổ sau mushroom, không phải đầu trong lòng chị khi tỉnh. C1/C2 kết truyện cũng thiếu vị trí đầu Alice ở thời điểm hỏi. |
| hybrid_plain/t06 | Thiếu evidence; hybrid; C1=unit31, C2=unit32, C3=unit38 | Not enough evidence in the provided documents. | abstention=True; Đầu ra cuối từ chối số điện thoại Queen, không thêm khẳng định vô căn cứ. |
| hybrid_plain/t07 | Thiếu evidence; hybrid; C1=unit42, C2=unit44, C3=unit41 | The Mock Turtle's exact home street address and house number is 11, unit 42. [C2:unit44] | abstention=False; Bịa địa chỉ 11, unit 42 bằng metadata nguồn/đơn vị. C2 đơn vị 44 chỉ nói về hát Turtle Soup, không có địa chỉ hay số nhà. Không được suy địa chỉ từ catalog eBook #11 hoặc unit ID. |

Citation trong bảng được rút thành Cn:unit để dễ đọc; `agent.json` giữ ID đầy đủ và `context_rows` ánh xạ ngược về văn bản gốc. Đối chiếu câu hỏi/đáp án kỳ vọng trong [benchmark](../../benchmark/cases.json), context/câu trả lời trong từng `agent.json` và nhãn/lý do trong `reviews.json` cùng thư mục kết quả.

### Đường dẫn minh chứng và tái lập

- [Protocol](../../benchmark/protocol.json), [benchmark](../../benchmark/cases.json), [hash đầu vào](../../benchmark/frozen_inputs.json), [selection trước test](../../results/selection.json).
- `results/dev/<cấu hình>/`: `retrieval.json`, `retrieval_summary.json`, `agent.json`, `reviews.json`, `agent_summary.json` cho cả 5 cấu hình.
- `results/test/<cấu hình>/`: cùng các file cho baseline và cấu hình chọn, đủ 7 câu mỗi cấu hình.
- [Thông tin lần chạy](../../results/run_info.json), [kiểm tra bài nộp](../../results/verification.json), [nhật ký lỗi kỹ thuật](../../artifacts/execution_errors.json). Hướng dẫn chạy nằm ngay bên dưới.

Kiểm thử code: `python -m unittest discover -s tests -v`. Các test offline/mock kiểm tra logic, tách split, nguồn, budget và citation; chất lượng benchmark ở trên đến từ Qdrant/embedding/model thật. Lệnh tái lập và thứ tự select/test ở phần hướng dẫn bên dưới. Không ghi đè kết quả đã nộp để chọn lại theo test; dùng checkout/thư mục thí nghiệm mới khi muốn thay pipeline.

### Chạy trên Windows PowerShell

Python 3.11+. Từ thư mục gốc repo, tạo môi trường riêng:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

`requirements-lock.txt` ghi phiên bản toàn bộ môi trường lần chạy nộp (dùng lại Python environment Day 6). Có thể cài lock thay requirements để tái lập dependency gián tiếp.

Nếu clone mới, tái tạo index và tải đúng model đã ghi trong manifest:

```powershell
.\.venv\Scripts\python.exe -B scripts/rebuild_index.py
.\.venv\Scripts\python.exe -B scripts/cache_embedding.py
.\.venv\Scripts\python.exe -B scripts/setup_local_model.py
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start_local_model.ps1
```

`rebuild_index.py` từ chối ghi đè index đã tồn tại. Nếu `.qdrant/` và cache/model đã có trên máy hiện tại, chỉ cần khởi động server. `start_local_model.ps1` mở tiến trình ẩn và chỉ bind localhost; log/PID ở `.runtime/`. Chờ server tải model trước khi gọi agent. Khi dùng xong, dừng đúng tiến trình theo PID và kiểm tra đường dẫn:

```powershell
$localModelProcessId = [int](Get-Content .runtime/server.pid)
$localModelProcess = Get-Process -Id $localModelProcessId -ErrorAction SilentlyContinue
$expectedModelServer = (Resolve-Path .runtime/llama/llama-server.exe).Path
if ($localModelProcess -and $localModelProcess.Path -eq $expectedModelServer) {
    Stop-Process -Id $localModelProcessId
}
```

Demo câu bất kỳ, mặc định dùng cấu hình đã chọn trên dev:

```powershell
.\.venv\Scripts\python.exe -B -m src.ask "What was in the jar labelled ORANGE MARMALADE?"
.\.venv\Scripts\python.exe -B -m src.ask "What is the White Rabbit's exact annual salary in pounds?"
```

### Kiểm tra và tái lập benchmark

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -B scripts/check_submission.py
```

Test offline/mock chỉ kiểm tra code; chất lượng phải xem trace embedding/Qdrant/model thật. Nhãn ngữ nghĩa hiện do **Codex AI đọc nguồn**, chưa được học viên hoặc người chấm độc lập xác nhận. Cần đọc từng `agent.json` (context và câu trả lời), đối chiếu `benchmark/cases.json` và xác nhận từng `reviews.json` trước khi nộp; không nhận các nhãn này là đánh giá thủ công đã được học viên thực hiện.

Máy lần chạy có 7,77 GiB RAM và tải bộ nhớ cao; model 1.5B từng rất chậm. Lượt chính dùng 0.5B và query embeddings thật đã tiền xử lý riêng ở `artifacts/query_vectors_dev.json` / `query_vectors_test.json`. `scripts/cache_queries.py --split dev` tái tạo cache dev bằng encoder thật; test chỉ tiền xử lý sau khi chốt cấu hình. Tải/cài/khởi động model và preprocessing được báo riêng với thời gian agent. Model server đã được dừng sau benchmark để trả lại RAM; chạy script start khi cần demo.

Để chạy lại mà giữ kết quả nộp, dùng thư mục mới, ví dụ `results-rerun`. Mọi lệnh của cùng thí nghiệm phải dùng cùng `--results-dir`. File đã có được giữ để resume; chọn tên thư mục mới nếu muốn chạy hoàn toàn mới.

```powershell
.\.venv\Scripts\python.exe -B scripts/run_benchmark.py retrieval --split dev --results-dir results-rerun
.\.venv\Scripts\python.exe -B scripts/run_benchmark.py agent --split dev --results-dir results-rerun
```

Sau đó **đọc và chấm** từng câu dev vào `results-rerun/dev/<config>/reviews.json` theo schema của các file nhãn đã nộp. Không dùng nhãn cũ nếu câu trả lời mới khác. `answer_grade`/`context_grade` 0–2, `citation_support` một boolean cho mỗi citation, `abstention_correct` cho câu thiếu evidence; thêm lý do và quote hỗ trợ.

Chỉ sau khi có đủ nhãn dev:

```powershell
.\.venv\Scripts\python.exe -B scripts/run_benchmark.py select --results-dir results-rerun
$chosenConfig = (Get-Content -Raw -Encoding UTF8 results-rerun/selection.json | ConvertFrom-Json).selected_config
.\.venv\Scripts\python.exe -B scripts/run_benchmark.py retrieval --split test --configs dense $chosenConfig --results-dir results-rerun
.\.venv\Scripts\python.exe -B scripts/run_benchmark.py agent --split test --configs dense $chosenConfig --results-dir results-rerun
```

Chấm đủ 7 câu test cho cả baseline/cấu hình chọn, rồi chạy `summarize --split test --configs dense $chosenConfig --results-dir results-rerun`. Không chọn/chỉnh bằng test. Chạy lại test đã công khai chỉ là kiểm tra tái lập; không coi là đánh giá độc lập mới nếu dùng để chỉnh.

`scripts/build_report.py`, `scripts/check_submission.py` mặc định dùng bài nộp ở `results/`. Báo cáo giữ cả kết quả không cải thiện, citation sai và từ chối nhầm; không coi tỷ lệ retrieval là độ chính xác trả lời của model.


## Thử thách nâng cao (nếu thực hiện)

**Không thực hiện.** Corpus text hiện tại không phải một tài liệu thực tế từ 100 trang có bảng, ảnh và biểu đồ; không có benchmark multimodal riêng 30 câu test. Không yêu cầu cộng 15 điểm bonus và không áp ngưỡng 90% của phần nâng cao cho kết quả cơ bản.

## Kết luận và giới hạn

Đã triển khai dense Day 6, BM25, hybrid RRF và một cấu hình context lớn; dùng model local thật cho toàn bộ agent benchmark. Chọn `hybrid_plain` trên dev rồi chạy baseline/cấu hình chọn trên test mới. Kết quả thấp hoặc thí nghiệm không tăng điểm được giữ nguyên, không suy tỷ lệ retrieval thành tỷ lệ trả lời đúng.

Giới hạn: một cuốn sách tiếng Anh, 5 câu test có đáp án nên mỗi câu tương ứng 20 điểm phần trăm; câu thiếu evidence còn khá dễ. Cùng AI hỗ trợ tạo benchmark và chấm gây nguy cơ thiên lệch, cần học viên đọc lại và người chấm độc lập xác nhận. Không đo tiếng Việt, OCR, bảng/ảnh, nhiều tài liệu, concurrency hoặc nhiều lần chạy. Một chunk Day 6 vượt giới hạn 256 token encoder đã được công bố ở bài trước; không sửa chunk/index sau khi nhìn test. JSON schema bảo đảm định dạng, không bảo đảm đúng ngữ nghĩa hoặc không hallucinate. Chưa tự động kiểm chứng mọi mệnh đề bằng một nguồn ngoài benchmark.

Trước khi nộp, học viên cần xác nhận nhãn/nguồn, hiểu code và kết quả, đồng thời bảo đảm giảng viên có quyền xem repo. Không tự nhận số điểm hay audit độc lập khi chưa được giảng viên đánh giá.
