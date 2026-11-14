# Báo cáo Day 7 — Vũ Quang Dũng — 2A202603486 — L3A

## Dữ liệu và cách chạy

Bài này dùng lại **corpus, ID chunk, embedding và vector store thật của Day 6**.
Corpus là tám chương Python Tutorial từ CPython **v3.13.0**: controlflow,
datastructures, modules, inputoutput, errors, classes, stdlib và stdlib2.
Có **186.787 ký tự, 93 đơn vị nguồn không chồng lặp, 256 chunk strategy B**.
Đây là nguồn text/RST, không phải PDF; `page` là ID đơn vị như `modules:004`,
không nhận là số trang vật lý. Mỗi đơn vị nguồn có ít nhất 1.500 ký tự chuẩn hóa.

[Manifest](../../data/day6_manifest.json) giữ URL, thời điểm truy cập, SHA-256,
offset và quy tắc đếm của Day 6. [Nguồn gốc và giấy phép](../../data/SOURCES.md)
trỏ tới raw/normalized text và PSF License Version 2; ví dụ code có điều khoản
0BSD theo tài liệu gốc. Người chấm có thể mở nội dung đã kèm hoặc tải đúng tag.
Code/dữ liệu hash-heuristic trước đây được lưu riêng trong `legacy`, không dùng
để báo kết quả phần này.

Embedding thật: **sentence-transformers/all-MiniLM-L6-v2**, revision
`1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, **384 chiều**, L2-normalized,
max sequence length 256 token, chạy CPU. Query dùng cùng encoder và tokenizer.
Store là **Chroma 1.5.9 persistent, collection day06_b, cosine HNSW** của Day 6.
Đã đối chiếu đủ ID/text/page và xuất vector thật vào
[day6_index.json](../../src/day6_index.json); script setup khôi phục Chroma từ
snapshot này. Hash file model được kiểm tra theo manifest. Không dùng vector hash,
ngẫu nhiên hay kết quả mock để tính benchmark.

Agent dùng model thật **gpt-6.1-sol**, `reasoning_effort=low`, qua Responses API.
Model gọi tool `search`, nhận context, có thể viết lại query và tìm tiếp trong
ngân sách. Lượt đầu luôn chạy câu hỏi gốc; filter chỉ lấy từ điều kiện người hỏi.
Agent không nhận `gold`, expected answer, nhãn answerable hoặc absence reason.
Source text được coi là dữ liệu, không phải chỉ dẫn.

Lệnh cài và chạy từng giai đoạn: [RUNBOOK](../../RUNBOOK.md). Phiên bản thực chạy:
[runtime.json](../../results/runtime.json); log môi trường/lỗi ban đầu:
[ENVIRONMENT.md](../../results/ENVIRONMENT.md). API đã được tác giả cho phép dùng.
Không ghi khóa vào code, trace hay báo cáo.

## Benchmark và kỷ luật dev/test

[24 câu](../../data/questions.json): **dev 15 có đáp án + 2 thiếu bằng chứng;
test 5 có đáp án + 2 thiếu bằng chứng**. Mỗi câu có đáp án kèm đáp án mong đợi,
nguồn, unit/page và quote. Quote được đối chiếu trên đúng source/page sau khi
gộp whitespace. Câu thiếu bằng chứng gần chủ đề, có lý do và kiểm tra toàn corpus,
không suy sự vắng mặt chỉ từ top-k.

Chỉ dùng lại **dev Day 6**; không dùng lại test Day 6 đã quan sát. Test Day 7 được
soạn mới. Trước test, phát hiện T03 trùng ý với dev Q11 nên thay bằng câu về thứ tự
tìm module; giữ [freeze ban đầu](../../data/benchmark_freeze_v1.json) và ghi lý do
trong [freeze hiện hành](../../data/benchmark_freeze.json). Không có test query nào
được chạy trước lần sửa này. Dev và tiêu chí chọn giữ nguyên.

Tiêu chí đã khai báo: ưu tiên grounded-answer mean trên dev; sau đó abstention
đúng, ít từ chối nhầm, ít token, rồi thứ tự ưu tiên đã ghi. Đã chốt
**hybrid-wide lúc 16:05:17 ngày 14/11/2026, UTC+7**, khi số test query đã chạy là 0.
[selection.json](../../results/selection.json) giữ cấu hình và hash mọi trace,
nhãn, summary dev. Sau đó mới chạy baseline và cấu hình chọn trên cùng test.
Không sửa cấu hình theo test.

## Retrieval và các cấu hình

Ba phương pháp: dense Chroma; lexical TF-IDF; hybrid RRF với `k=60`, hợp nhất
dense top-10 và lexical top-10 theo rank, không cộng trực tiếp hai thang score.
Metadata filter cùng điều kiện cho cả hai nhánh. Kết quả giữ ID, text, source,
page/unit, metadata và score. Không triển khai tất cả phương pháp gợi ý vì đề
chỉ yêu cầu ít nhất ba phương pháp.

Hit@1 và Evidence Hit@3 dùng **cùng câu hỏi gốc và cùng cutoff**, kể cả khi agent
lấy top-5. Hit cần một chunk đúng nguồn/page chứa trọn quote. Context Evidence
Rate (CER) là đủ quote trong context cuối. Tất cả tỷ lệ retrieval chỉ tính câu
có đáp án. Đọc ngữ nghĩa/context 0–2 được báo riêng, không đồng nhất với khớp quote.

| Cấu hình | Method; top-k; context ký tự; tối đa search | Split | Hit@1 | Evidence Hit@3 | CER cuối agent | Trung bình giây/câu |
|---|---|---|---|---|---|---|---|
| Baseline | Dense; 3; 3.200; 1 | dev | 9/15 (60%) | 13/15 (86,67%) | 13/15 (86,67%) | 5,12 |
| Lexical | TF-IDF; 3; 3.200; 1 | dev | 12/15 (80%) | 13/15 (86,67%) | 13/15 (86,67%) | 4,94 |
| Hybrid | RRF; 3; 3.200; 1 | dev | 11/15 (73,33%) | 13/15 (86,67%) | 13/15 (86,67%) | 5,07 |
| Cải thiện dense-wide | Dense; 5; 6.000; 2 | dev | 9/15 (60%) | 13/15 (86,67%) | 13/15 (86,67%) | 5,54 |
| Cải thiện hybrid-wide | RRF; 5; 6.000; 2 | dev | 11/15 (73,33%) | 13/15 (86,67%) | 14/15 (93,33%) | 5,24 |
| Baseline | Dense; 3; 3.200; 1 | test | 4/5 (80%) | 5/5 (100%) | 5/5 (100%) | 5,19 |
| Cấu hình đã chọn | RRF; 5; 6.000; 2 | test | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5,36 |

Giả thuyết dense-wide: thêm candidate/context và một lượt tìm tiếp sẽ phục hồi
điều kiện bị thiếu. Giả thuyết hybrid: từ khóa định danh Python bổ sung cho
semantic search. Hybrid-wide kết hợp hai thay đổi. Không đổi corpus, encoder,
model, gold hay filter giữa các cấu hình.

[Retrieval dev](../../results/retrieval/dev/summary.json) và
[retrieval test](../../results/retrieval/test/summary.json) đo riêng ba phương pháp
với top-3/budget 3.200. TF-IDF test đạt Hit@1 3/5, Hit@3 5/5; đây là đối chiếu
retrieval bổ sung, không dùng để chỉnh hoặc chọn lại sau test. Thời gian retrieval
riêng nằm trong trace; warmup/cache và thứ tự đo khác nhau nên không suy tốc độ
tổng quát từ một lượt chạy.

## Agent, context và nhãn

Context giữ nguyên chunk và nguồn, dedup theo ID, không cắt mất điều kiện giữa
chunk; chunk không vừa budget bị bỏ. Nếu tìm lại, ưu tiên candidate của lượt mới
rồi bổ sung candidate cũ còn vừa. Chỉ context tích lũy mới nhất được gửi lại;
ngữ cảnh tool cũ được thay bằng ghi chú đã supersede. Trace giữ tất cả kết quả.
Model dừng bằng answer/abstain, hoặc hệ thống dừng khi hết search/model budget.
Citation phải nằm trong context cuối và xuất hiện trong câu trả lời; hỗ trợ ngữ
nghĩa được chấm riêng. Citation nằm trong câu từ chối cũng được đếm.

Lỗi provider/retriever được ghi riêng và dừng batch; không thay bằng câu trả lời
giả. Năm lỗi HTTP 400 đầu phiên do SDK dùng tên trường `async_` thay alias API
đã được lưu trong `errors.json`; đã sửa serialization trước lượt dev thành công.
Các lần thành công bên dưới không có provider error. Khi resume lỗi, lịch sử
lỗi vẫn được giữ; đổi cấu hình, prompt, corpus hoặc câu hỏi sẽ bị từ chối resume.

| Cấu hình/split | Tool use | Grounded số câu 0/1/2; mean /2 | Citation hỗ trợ | Câu trả lời có citation | Abstention đúng | Từ chối nhầm | Context 0/1/2 |
|---|---|---|---|---|---|---|---|
| Baseline/dev | 17/17 | 1/1/13; 1,80 | 15/16 | 14/14 | 2/2 | 1/15 | 0/2/13 |
| Lexical/dev | 17/17 | 1/0/14; 1,87 | 16/16 | 14/14 | 2/2 | 1/15 | 0/1/14 |
| Hybrid/dev | 17/17 | 1/0/14; 1,87 | 16/16 | 14/14 | 2/2 | 1/15 | 0/1/14 |
| Dense-wide/dev | 17/17 | 1/0/14; 1,87 | 16/16 | 14/14 | 2/2 | 1/15 | 0/1/14 |
| Hybrid-wide/dev | 17/17 | 0/0/15; 2,00 | 17/17 | 15/15 | 2/2 | 0/15 | 0/0/15 |
| Baseline/test | 7/7 | 0/0/5; 2,00 | 6/6 | 5/5 | 2/2 | 0/5 | 0/0/5 |
| Hybrid-wide/test | 7/7 | 0/0/5; 2,00 | 6/6 | 5/5 | 2/2 | 0/5 | 0/0/5 |

Citation hỗ trợ tính cả citation trên câu từ chối; coverage chỉ tính câu trạng
thái answered. Mẫu số bằng 0 được xem là không áp dụng. Dense-wide dev tìm hai
lượt ở Q01 và Q11, còn 15 câu một lượt; các cấu hình khác trong lần đo đều một
lượt/câu, dù hybrid-wide được phép tối đa hai lượt. Mức tối đa không phải số lượt
model bắt buộc dùng.

Đã đọc đủ **5 câu test có đáp án và 2 câu thiếu bằng chứng cho cả hai cấu hình**,
kiểm tra nguyên văn nguồn, citation và chấm context 0/1/2. Mỗi nhãn có lý do và
hash trace. Nhãn do AI judge hỗ trợ, sau đó **Codex trực tiếp đọc đối chiếu**, không
phải xác nhận thủ công của tác giả. Baseline Q11 được hạ từ 2 xuống 1 vì citation
không đủ; lưu thay đổi trong [audit dev](../../results/codex-dev-review.json).
[Quyết định test](../../results/test_inspection_decisions.json) được ràng buộc với
hash đúng đầu ra đã đọc. Có [phiếu tự kiểm tra tùy chọn](../../results/author_review_pending.csv)
để tác giả ghi thêm xác nhận; không tự điền hoặc nhận là đã có human review.

## Hai lỗi dev và kết quả trước/sau

1. **Q01 — break trong vòng lặp lồng nhau.** Dense baseline top-3 chỉ lấy thảo luận
   loop-else; thiếu quy tắc vòng trong cùng nên agent từ chối, grade 0. Tăng context
   và tìm lại ở dense-wide lấy được ví dụ hai vòng lặp với output chứng minh vòng
   ngoài tiếp tục: chấp nhận suy luận có nguồn, grade 2, nhưng exact-quote metric
   vẫn miss. Hybrid-wide đưa trực tiếp đoạn quy tắc `controlflow:003` vào top-5,
   grade 2 và CER hit. Không tự đổi gold để làm metric tăng.
2. **Q11 — `__name__` khi chạy script.** Baseline trả đúng giá trị nhưng cite
   `classes:003`, chỉ nói top-level code thuộc module `__main__`, chưa thiết lập
   phép gán biến; chấm một phần, citation không đủ. Dense-wide tìm lại vẫn không
   có đoạn rõ nên từ chối, grade 0: một thay đổi có thể làm câu này xấu đi. Hybrid
   và hybrid-wide lấy được guard `if __name__ == "__main__"` cùng giải thích chạy
   main file ở `modules:004`, nên grade 2. Quote gold nguyên văn ở unit khác không
   nằm trong context, vì thế semantic context 2 vẫn đi cùng CER miss ở câu này.

Theo tiêu chí đã khai báo, hybrid-wide có grounded mean dev 2,00 và từ chối nhầm
0/15, nên được chọn. Cấu hình này không có grounded failure trên dev lần đo, nhưng
tốn nhiều input token hơn baseline. Không kết luận mọi thay đổi đều có lợi.

## Ví dụ và chi phí

- **T02 có bằng chứng:** cả hai cấu hình trả lời `enumerate()` trả index và value,
  cite chunk `41d7ef430bff9aceed5ce03921b39a36712b19b8b7eef8dfb2d7083e67927a9c`,
  nguồn `datastructures:010`. Đọc paragraph và ví dụ xác nhận đủ hai thành phần.
- **T-U02 thiếu bằng chứng:** từ chối đưa độ dài khóa AES; chỉ nhắc cảnh báo pickle
  có thể chạy code từ nguồn không tin cậy, được đoạn `inputoutput:010` hỗ trợ.
  Không bịa số bit, và kiểm tra toàn corpus không có khuyến nghị AES.
- **Lỗi:** baseline/dev Q11 ở trên minh họa đáp án đúng nhưng citation yếu;
  ID trong context không tự chứng minh toàn bộ khẳng định.

| Cấu hình/split | Input token thực | Output token thực | Trung bình giây/câu | Agent USD ước tính trước hệ số nhóm |
|---|---|---|---|---|
| Baseline/dev | 25.869 | 2.720 | 5,12 | 0,072615 |
| Dense-wide/dev | 41.245 | 2.730 | 5,54 | 0,109790 |
| Hybrid/dev | 25.484 | 2.694 | 5,07 | 0,077908 |
| Hybrid-wide/dev | 36.892 | 2.705 | 5,24 | 0,097201 |
| Lexical/dev | 25.404 | 2.669 | 4,94 | 0,075372 |
| Baseline/test | 10.918 | 1.012 | 5,19 | 0,031956 |
| Hybrid-wide/test | 14.932 | 984 | 5,36 | 0,039704 |

Đây là token provider trả về của các lần agent thành công, gồm cả reasoning khi
provider tính vào output; không suy từ số ký tự. Cached input nằm trong summary.
Audit token được lưu riêng trong reviews, không cộng vào bảng agent. Probe ban
đầu/lần lỗi chưa có đầy đủ usage, nên bảng không đại diện toàn bộ hóa đơn.
Đã bổ sung [bảng chi phí có thể tính lại](../../results/costs.json), dùng
[snapshot giá công khai ModelAPI](../../data/pricing/modelapi-gpt-6.1-sol.json)
ngày 14/11/2026. Nguồn: https://api.modelapi.vn/api/pricing. Mức standard trước
hệ số nhóm: input không cache 2 USD/triệu token, output 10 USD/triệu, cache read
0,10 USD/triệu; từ 500.000 input token/request lần lượt 4/15/0,20. Tính theo
từng model call, không lấy tổng token batch để chọn tier. Không chạy request nào
của bài này tới ngưỡng long-context.

Tổng agent đã ghi usage ước tính **0,504546 USD**, AI audit đã giữ usage
**0,459999 USD**, tổng **0,964545 USD** trước hệ số nhóm. Bảng giá hiện công bố
hệ số các nhóm dùng được cho model từ 0,9 đến 2,6; tổng tương ứng khoảng
**0,868090–2,507817 USD**. Nhóm thực tế của tài khoản, giá lúc chạy, ưu đãi và
các probe/attempt thiếu usage chưa xác minh, nên đây là **ước tính áp bảng giá
hiện tại, không phải hóa đơn thực trả**. Summary/trace đã khóa giữ nguyên byte
và `cost_usd: null` lịch sử; `costs.json` bổ sung chi phí, hash trace/review và
công thức để kiểm lại. Embedding/retrieval local chưa quy đổi điện/phần cứng.

## Tái lập, giới hạn và kết luận

Trace, context, output gốc, model response ID, tham số và usage theo từng câu ở
`results/<cấu-hình>/<split>/traces.json`; nhãn ở `reviews.json`, tổng hợp ở
`summary.json`. [Verifier](../../scripts/verify_submission.py) kiểm freeze, nguồn,
offset chunk, quote, vector/dimension, nhãn đúng trace và đủ cả baseline/selected
test và chi phí gắn với đúng usage. Kết quả kiểm ở [verification.json](../../results/verification.json).
Unit tests gồm starter và regression cho cutoff, provenance, tool calling,
citation ngoài context, resume sai input và lỗi kết nối; mock chỉ dùng kiểm code.
Đã bổ sung kiểm tra thí nghiệm ở thư mục riêng, selection sau khi chuyển đường
dẫn, reviewer có tên và tính cache/context-tier. Lần kiểm chứng hiện tại dùng
`.venv` trong project, khôi phục Chroma vào thư mục mới từ export, so vector do
encoder thật sinh với vector Day 6 và chạy retrieval thật; chi tiết ở
[current_validation.json](../../results/current_validation.json). Không cần
virtualenv của project Day 6 và không gọi lại model API cho bước kiểm chứng này.

Test nhỏ: 5 câu có đáp án và 2 câu thiếu bằng chứng; cả baseline và selected đều
đạt đầy đủ nên **chưa chứng minh hybrid-wide tốt hơn baseline trên test**. Dev và
test cùng tài liệu, có chia sẻ từ vựng; không phải document-disjoint. Chỉ một lần
generation/query, không ước lượng phương sai. So sánh thời gian chịu ảnh hưởng
mạng/cache/thứ tự chạy. MiniLM 256 token có thể truncate cuối chunk Day 6; HNSW là
approximate và có thể thay đổi tie khi tái tạo. Gold chưa liệt kê hết bằng chứng
tương đương. Judge và Codex đều là AI, không thay thế tác giả hoặc người chấm độc lập.

Runner hỗ trợ `--results-root` xuyên suốt dev, audit, review, select, test, chi phí
và verifier. Có thể chạy lại ở `.runs/replay-01` mà không sửa `results/` đã nộp;
`select --resume` xác minh cấu hình đã chốt thay vì báo lỗi. Model/key/URL lấy
từ `.env`; đổi model/reasoning cần đo dev và chọn lại ở thư mục mới. Nhãn mới
cần được reviewer có tên kiểm tra và phê duyệt, không bắt buộc cờ mang tên Codex.
Tái lập trên benchmark đã công khai không được nhận là test ẩn độc lập mới.

Phần cơ bản đã có code, ba retriever, model thật, thí nghiệm dev, lựa chọn trước
test, trace/nhãn, chi phí ước tính có nguồn và báo cáo tái lập. Phần **100 trang đa phương thức +15 điểm không
thực hiện**, không nhận bonus hoặc suy điểm từ độ chính xác bộ test cơ bản.
Không tự nhận đã nộp link cho giảng viên hoặc đã có người chấm độc lập. Tác giả
chịu trách nhiệm đọc bài và nộp qua kênh lớp. Mọi giới hạn và kết quả không cải
thiện được giữ trong bài.
