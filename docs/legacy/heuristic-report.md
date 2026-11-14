# Báo cáo Day 7 — VuQuangDung (2A202603486)

## Dữ liệu và benchmark

- Nguồn, quyền sử dụng, số trang và số chunk: 3 tài liệu nội bộ tự tạo (quy-định-đào-tạo, nội-quy-thư-viện, chính-sách-tài-chính), 32 chunks, dữ liệu tự tạo nên được phép chia sẻ công khai.
- Vector store, embedding model, phiên bản và số chiều: file JSON `src/day6_index.json`, embedding `hashed-tfidf-v1 (offline, deterministic)`, version `day6-v1`, số chiều 256. Query và doc dùng chung hàm `embed` trong `src/day6_store.py` nên tương thích index.
- Agent model, cách chạy và phân chia dev/test: `HeuristicController` (baseline minh bạch, thay được bằng LLM mà không đổi Retriever/trace) + `DenseRetriever` trên index Day 6. Dev: 15 có đáp án + 2 thiếu evidence. Test: 5 có đáp án + 2 thiếu evidence.
- Cách xác định câu có/thiếu evidence và tiêu chí chấm: câu có đáp án có `gold` nằm trọn trong 1 chunk đúng nguồn/trang; câu thiếu evidence là câu gần chủ đề nhưng tài liệu không quy định, `answerable: false`. Chấm theo BENCHMARK.md: answer_grade 0/1/2, citation_support từng citation, abstention_correct.

## Retrieval và thử nghiệm

| Cấu hình | Phương pháp, top-k, filter, rerank, context budget | Giả thuyết / thay đổi | Split | Hit@1 | Evidence Hit@3 | Context Evidence Rate | Thời gian / chi phí |
|---|---|---|---|---|---|---|---|
| Baseline | TF-IDF lexical, top-k 3, budget 800 ký tự | gốc | dev | 15/15 (100%) | 15/15 (100%) | 15/15 (100%) | ~0.03 ms/câu, 0 USD |
| Phương pháp 2 | Dense hashed-embedding Day 6, top-k 3, budget 800 | vector tương tự bắt được diễn đạt khác từ | dev | 15/15 (100%) | 15/15 (100%) | 15/15 (100%) | 0 USD (offline) |
| Phương pháp 3 | Hybrid RRF (dense top-10 + TF-IDF top-10), top-3, budget 800 | kết hợp bù điểm yếu nhau | dev | 15/15 (100%) | 15/15 (100%) | 15/15 (100%) | 0 USD (offline) |
| Cải thiện 1 (retrieval) | Dense top-k 5, budget 1500 | tăng recall cho câu cần nhiều evidence | dev | 15/15 (100%) | 15/15 (100%) | 15/15 (100%) | 0 USD |
| Cải thiện 1 (agent) | Dense + ngưỡng abstain 0.40, top-k 3, budget 800 | từ chối khi top-1 score < 0.40 | dev | — | — | — | answered 16/17, abstain 1/17 |
| Cải thiện 2 (agent) | Dense + ngưỡng abstain 0.45, top-k 5, budget 1500, max_searches 3 | ngưỡng chặt hơn + context rộng | dev | — | — | — | answered 14/17, abstain 3/17 |
| Cấu hình đã chọn | Dense + ngưỡng 0.40, top-k 3, budget 800, max_searches 2 | ưu tiên từ chối nhầm = 0 | test | (chạy sau chấm tay dev) | | | |
| Baseline | TF-IDF top-k 3 | đối chứng | test | (chạy sau chấm tay dev) | | | |

Hai lỗi dev (đọc từ trace dev):

1. Dataset quá dễ → retrieval bão hòa: 15/15 cả 3 phương pháp (TF-IDF, dense, hybrid-RRF). Nguyên nhân: câu hỏi dùng gần nguyên văn từ trong chunk nên lexical đã trúng hết, không phân biệt được phương pháp. Kết quả âm tính này được báo trung thực; không "làm khó" dataset sau khi đã đo để tránh rò rỉ chỉnh-benchmark.
2. Score câu thiếu evidence chèn vào nhóm có đáp án: d-u02 ("mượn laptop", 0.4364) cao hơn cả câu có đáp án d12 (0.4252) vì embedding hash trùng từ chung ("sinh viên", "thư viện", "mượn"). Hệ quả: không tồn tại ngưỡng tách sạch cả hai → phải đánh đổi. Ngưỡng 0.10: abstain đúng 0/2, từ chối nhầm 0/15. Ngưỡng 0.40: abstain đúng 1/2, từ chối nhầm 0/15. Ngưỡng 0.45: abstain đúng 2/2 nhưng từ chối nhầm 1/15 (mất câu d12).

Lý do chọn cấu hình: chốt ngưỡng **0.40 + dense top-k 3 + budget 800** vì tiêu chí công bố trước là **từ chối nhầm = 0** (trả lời sai câu có đáp án hại hơn bỏ sót câu thiếu evidence); chi phí 0 USD và thời gian ~ms nên không phải đánh đổi thêm. Chốt trước khi chạy test.

## Agent và đánh giá

- Tool, số lượt gọi, điều kiện dừng, cách chọn context và xử lý lỗi: 1 tool `search` (dense trên index Day 6), `max_searches=2`, dừng sau 1 lượt search ở baseline; abstain khi context rỗng hoặc top-1 score < ngưỡng (0.40 ở cấu hình chốt); context cộng dồn qua các lượt, dedup theo ID, cắt theo budget 800 ký tự; citation là chunk top-1 kèm nguyên văn text + `[id]`; lỗi retriever ghi `status: error`, không thay kết quả giả.

| Cấu hình / split | Tool use | Số lượt gọi | Grounded answer 0/1/2 và trung bình | Citation hợp lệ | Câu có citation | Abstention đúng | Từ chối nhầm |
|---|---|---|---|---|---|---|---|
| (điền từ summary.json) | | | | | | | |

| Query ID | Loại câu | Tool call và kết quả | Câu trả lời và citation | Nhãn, lý do |
|---|---|---|---|---|
| | | | | |

- Đường dẫn trace, nhãn, lệnh chạy, thời gian và chi phí: `starter/results/agent-dev-t040/traces.json` (dev chốt), `starter/results/agent-test/traces.json` (test), `data/reviews-dev.json`, `data/reviews-test.json`, `starter/results/*/summary.json`; lệnh trong [RUNBOOK.md](../../RUNBOOK.md) hoặc `bash scripts/run_all.sh`; offline nên chi phí 0 USD, thời gian từ `elapsed_ms` trong trace. Lưu ý: `starter/results/` đang bị `.gitignore` — khi nộp, `git add -f` các file kết quả hoặc ghi cách tái tạo.
- Kết quả trước/sau, ví dụ lỗi, đánh đổi và giới hạn: ngưỡng 0.10 → 0.40: abstain đúng 0/2 → 1/2, từ chối nhầm giữ 0/15; ngưỡng 0.45: abstain đúng 2/2 nhưng từ chối nhầm 1/15 (mất d12) nên loại. Giới hạn: (a) embedding hash offline yếu với từ đồng nghĩa, câu hỏi diễn đạt khác từ có thể rớt score; (b) dataset dev dễ nên retrieval bão hòa, chưa chứng minh hybrid hơn dense; (c) controller heuristic trích top-1, chưa viết lại câu trả lời — thay bằng LLM + giữ nguyên Retriever/trace là bước tiếp theo.

## Thử thách nâng cao (không thực hiện)

- Không làm phần 100 trang trong phạm vi bài này.
