# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Mai Văn Quân  
**Vai trò trong nhóm:** Trace & Docs Owner (Sprint 4)  
**Ngày nộp:** 14/04/2026  
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi phụ trách phần nào?

**Module/file tôi chịu trách nhiệm:**
- File chính: `eval_trace.py`, `docs/routing_decisions.md`, `docs/single_vs_multi_comparison.md`, `docs/system_architecture.md`.
- Functions tôi implement: `run_evaluation`, `analyze_traces`, `generate_grading_log` (tổng hợp kết quả và phân tích số liệu).

**Cách công việc của tôi kết nối với phần của thành viên khác:**
Tôi là người "về đích" cho dự án nhóm. Tôi nhận `graph.py` của Thái, các worker của Ánh và MCP Server của Huy để thực hiện tích hợp cuối cùng. Tôi đảm bảo mô hình có thể chạy được trên môi trường Windows, giải quyết các xung đột state giữa các agent, và cuối cùng là thực hiện chạy 15 câu test để thu thập "bằng chứng" (traces) cho việc so sánh hiệu quả giữa kiến trúc Single-agent (Day 08) và Multi-agent (Day 09).

**Bằng chứng:**
Tôi đã hoàn thiện file `eval_trace.py` để tự động hóa việc chạy test suite và lưu trữ kết quả phân tích vào thư mục `artifacts/traces/`. Tôi cũng cấu hình `sys.stdout` sử dụng `utf-8` để hiển thị tiếng Việt trên PowerShell.

---

## 2. Tôi đã ra một quyết định kỹ thuật gì?

**Quyết định:** Sử dụng cơ chế mapping an toàn từ Worker Output vào AgentState trung tâm thay vì cho phép Worker tự sửa đổi State.

**Lý do:**
Khi tích hợp Sprint 4, tôi phát hiện lỗi `AttributeError: 'dict' object has no attribute 'append'` do `policy_tool_worker` vô tình trả về một Dictionary đè lên danh sách `worker_io_log` của hệ thống. Thay vì yêu cầu các thành viên khác sửa lại code có tính rủi ro, tôi quyết định thực hiện "Sanitization" tại node Graph: Các worker chỉ trả kết quả thô, và chính code tại `graph.py` do tôi cập nhật sẽ map dữ liệu đó vào State.

**Trade-off đã chấp nhận:**
Điều này làm code ở Orchestrator dài hơn một chút, nhưng nó đảm bảo tính bền bỉ (Robustness). Nếu một worker bị lỗi hoặc trả về sai format, nó sẽ không làm "sập" toàn bộ trace xử lý của hệ thống.

**Bằng chứng từ trace/code:**
Trong `graph.py`:
```python
# Cấu trúc mapping an toàn do tôi thiết lập
worker_res = retrieval_run(state)
state["retrieved_chunks"] = worker_res.get("chunks", [])
state["workers_called"].append("retrieval_worker")
```

---

## 3. Tôi đã sửa một lỗi gì?

**Lỗi:** Case-sensitivity Bug trong Routing Logic (Lỗi mã `ERR-`)

**Symptom:**
Khi chạy câu hỏi `q09` của test suite với task chứa mã lỗi `ERR-403-AUTH`, Supervisor đã route nhầm sang `retrieval_worker` thay vì `human_review` (đúng ra phải trigger HITL).

**Root cause:**
Qua việc phân tích `route_reason` trong trace tôi thu thập được, tôi phát hiện Supervisor sử dụng pattern matching `task.contains("err-")` (viết thường), trong khi input của người dùng là `ERR-` (viết hoa). Mặc dù có lệnh `.lower()` nhưng vị trí kiểm tra pattern lại nằm trước khi lệnh này có hiệu lực hoàn toàn hoặc pattern so khớp không nhất quán.

**Cách sửa:**
Tôi đã cập nhật logic supervisor để normalize toàn bộ task sang lowercase trước khi thực hiện bất kỳ phép so khớp từ khóa nào. Đồng thời sửa các pattern trong routing rules sang chữ thường đồng nhất.

**Bằng chứng trước/sau:**
- Trước: `route_reason: "Defaulting to informational retrieval"` (Lỗi)
- Sau: `route_reason: "Manual review triggered for error code: err-403-auth"` (Đúng)
- Debug time: Nhờ trace log chỉ mất **3 phút** để tìm ra lỗi này thay vì phải đọc lại toàn bộ code.

---

## 4. Tôi tự đánh giá đóng góp của mình

**Tôi làm tốt nhất ở điểm nào?**
Tôi đã giải quyết được các bài toán "tương thích môi trường". Việc cấu hình `sys.stdout` UTF-8 và sửa lỗi `UnicodeEncodeError` đã cứu cả nhóm khỏi việc bị crash pipeline khi chạy log trên Windows.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**
Tôi chưa tối ưu được việc chạy worker song song (parallel execution). Hiện tại các worker vẫn chạy tuần tự nên latency cho câu multi-hop vẫn còn ở mức ~2.9s.

**Nhóm phụ thuộc vào tôi ở đâu?**
Tôi là người tạo ra các tài liệu phân tích (`comparison.md`, `architecture.md`). Nếu không có các số liệu so sánh định lượng của tôi (+33% accuracy cho multi-hop), nhóm sẽ không chứng minh được giá trị của việc chuyển sang Multi-agent.

**Phần tôi phụ thuộc vào thành viên khác:**
Tôi phụ thuộc 100% vào tính ổn định của MCP Server (Huy) và chất lượng Embedding (Ánh). Nếu dữ liệu đầu vào rác, phân tích của tôi sẽ không có giá trị.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì?

Tôi sẽ cài đặt **Parallel Node Execution** cho `retrieval_worker` và `policy_tool_worker`. Dựa trên trace của câu q15, việc hai worker này chạy tuần tự mất gần 3 giây. Nếu chạy song song, tôi có thể giảm latency xuống còn ~1.8s, giúp hệ thống tiệm cận với hiệu suất của Single-agent mà vẫn giữ được độ chính xác cao.
