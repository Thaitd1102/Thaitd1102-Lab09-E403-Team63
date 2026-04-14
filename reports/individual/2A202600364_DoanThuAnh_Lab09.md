# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Đoàn Thư Ánh
**MSSV:** 2A202600364
**Vai trò trong nhóm:** Worker Owner  
**Ngày nộp:** 2026-04-14  
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi phụ trách phần nào? (~130 từ)

Tôi phụ trách **Sprint 2 — Build Workers**: implement ba workers là execution layer của toàn bộ hệ thống multi-agent.

**Module/file tôi chịu trách nhiệm:**
- File chính: `workers/retrieval.py`, `workers/policy_tool.py`, `workers/synthesis.py`
- Functions tôi implement:
  - `retrieval.run(state)` — query ChromaDB, trả về chunks với ChromaDB similarity (1 - distance)
  - `policy_tool.run(state)` — detect exceptions, gọi MCP tools qua `dispatch_tool()`
  - `synthesis.run(state)` — gọi LLM grounded prompt, output có citation và confidence
  - `policy_tool._detect_exceptions(task)` — phân tích 5 loại exception case

**Cách công việc của tôi kết nối với phần của thành viên khác:**

Workers của tôi là "execution layer". Supervisor Owner quyết định *route đến worker nào*, còn tôi quyết định *làm gì sau khi nhận task*. `retrieval.run()` trả về `retrieved_chunks` là input trực tiếp cho `synthesis.run()`. `policy_tool.run()` trả về `policy_result` và `mcp_tools_used` cho synthesis tổng hợp và trace ghi nhận.

**Bằng chứng:** Comment `# Author: Worker Owner` ở đầu `workers/retrieval.py`. Timestamp: 2026-04-14T08:19.

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (~175 từ)

**Quyết định:** Trong `policy_tool.py`, tôi quyết định **không gọi ChromaDB trực tiếp** mà thay vào đó gọi qua `dispatch_tool("search_kb", ...)` từ MCP server — dù ChromaDB đã có sẵn trong workers/retrieval.py.

**Lý do:** Nếu policy_tool gọi ChromaDB trực tiếp, worker này vi phạm worker contract — contract quy định policy_tool phải gọi tools qua MCP interface, không access storage layer trực tiếp. Ngoài ra, nếu sau này search_kb được nâng cấp (thêm reranking, cache), policy_tool tự động hưởng lợi mà không cần sửa code.

**Các lựa chọn thay thế đã cân nhắc:**
1. Import `_collection` từ `retrieval.py` và query trực tiếp — nhanh, nhưng tạo coupling chặt giữa hai workers.
2. Tạo một ChromaDB client riêng trong `policy_tool.py` — dư thừa, tốn RAM.
3. **Tôi chọn:** Gọi `dispatch_tool("search_kb")` — tuân đúng contract, loose coupling.

**Trade-off đã chấp nhận:** Thêm ~200ms latency mỗi lần `search_kb` được gọi vì phải qua dispatch layer. Tuy nhiên đây là mức chấp nhận được vì policy queries không cần real-time response.

**Bằng chứng từ trace/code:**
```python
# workers/policy_tool.py — Author: Worker Owner
# Gọi MCP dispatch thay vì ChromaDB trực tiếp
call = dispatch_tool("search_kb", query=search_query, top_k=3)
mcp_tools_used.append(call)
policy_result["mcp_called"] = True
```
Trace `gq10` (Flash Sale refund): `mcp_tools_used: [{"tool": "search_kb", "timestamp": "2026-04-14T..."}]` — MCP call được ghi đầy đủ.

---

## 3. Tôi đã sửa một lỗi gì? (~165 từ)

**Lỗi:** `retrieval.py` có **legacy/dead return block** — hai lệnh `return` trong cùng một function path.

**Symptom:** Khi test worker độc lập:
```python
from workers.retrieval import run as retrieval_run
test_state = {"task": "SLA ticket P1 la bao lau?", "history": []}
result = retrieval_run(test_state)
print(result["retrieved_chunks"])
```
Chạy đúng vì Python không báo lỗi với legacy code block, nhưng IDE cảnh báo và code có hai `return` tại dòng 57–60 và 62–65. Nếu logic xử lý tiếp sau `return` đầu tiên bị di chuyển xuống, khối lệnh cũ sẽ bị bỏ qua hoàn toàn và trở thành dead code.

**Root cause:** Khi refactor từ draft ban đầu, đoạn `return retrieved_chunks, retrieved_sources` ở dòng 62–65 là sót lại từ phiên bản cũ — không bao giờ được thực thi.

**Cách sửa:** Xoá toàn bộ block return thứ hai (dòng 62–65), chuẩn hóa return duy nhất với đúng field names theo contract (`retrieved_chunks[:5]`, `retrieved_sources`, `worker_io_log`).

**Bằng chứng trước/sau:**
```diff
- return {
-     "retrieved_chunks": retrieved_chunks[:5],
-     "retrieved_sources": list(retrieved_sources)
- }
-         
- return {          # <- dead code, logic cũ
-     "retrieved_chunks": retrieved_chunks,
-     "retrieved_sources": list(retrieved_sources)
- }
+ return {
+     "retrieved_chunks": retrieved_chunks[:5],
+     "retrieved_sources": list(retrieved_sources),
+     "worker_io_log": worker_io_log   # <- thêm field theo contract
+ }
```
Sau fix: `python workers/retrieval.py` chạy, in đúng số chunks và `worker_io_log`.

---

## 4. Tôi tự đánh giá đóng góp của mình (~120 từ)

**Tôi làm tốt nhất ở điểm nào?**

Phần exception detection trong `policy_tool.py`. Tôi thiết kế `_detect_exceptions()` với 5 loại exception patterns riêng biệt, document rõ ràng và test được độc lập. Flash Sale và digital product exception observed correct in evaluation traces liên quan (q07 — license key, q10 — store credit, gq10 — Flash Sale). Policy worker xử lý đúng `policy_applies=False` và ghi rõ lý do vào `policy_result["details"]`.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**

`synthesis.py` — tôi chưa handle trường hợp LLM trả về JSON không đúng format (thiếu field `answer`). Hiện tại dùng `.get("answer", "")` nhưng chưa có fallback message rõ ràng khi parse lỗi.

**Nhóm phụ thuộc vào tôi ở đâu?**

Toàn bộ execution layer phụ thuộc vào ba workers của tôi. Nếu `retrieval.run()` trả về `retrieved_chunks=[]` (ChromaDB chưa được index), `synthesis.run()` sẽ abstain — graph không crash nhưng không trả lời được. Tôi đã implement keyword fallback trong retrieval để handle trường hợp này.

**Phần tôi phụ thuộc vào thành viên khác:**

Tôi cần Supervisor Owner set đúng `needs_tool=True` trong state khi task là policy query — nếu thiếu flag này, `policy_tool.run()` vẫn chạy được nhưng không biết có được phép gọi thêm external tools hay không (tôi đã implement để gọi MCP dựa vào keyword detection riêng, không phụ thuộc `needs_tool` flag để đảm bảo hoạt động độc lập).

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (~75 từ)

Tôi sẽ cải tiến `synthesis.py` bằng cách thêm **dynamic confidence threshold cho HITL**. Trace của câu q09 (ERR-403-AUTH) cho thấy `confidence=0.2` nhưng `hitl_triggered=False` — pipeline vẫn trả lời dù độ tin cậy rất thấp. Nếu implement logic `if confidence < 0.4: state["hitl_triggered"] = True` trong synthesis worker, câu q09 sẽ được escalate đúng thay vì trả lời mơ hồ. Đây là cải tiến có bằng chứng số liệu rõ ràng từ trace, không phải đoán mò.

---

*File: `reports/individual/worker_owner.md`*  
*Vai trò khai báo: Worker Owner — phụ trách `workers/retrieval.py`, `workers/policy_tool.py`, `workers/synthesis.py` (Sprint 2)*
