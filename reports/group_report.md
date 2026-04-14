# Báo Cáo Nhóm — Lab Day 09: Multi-Agent Orchestration

**Tên nhóm:** 63  
**Thành viên:**
| Tên | Vai trò | MSSV |
|-----|---------|-------|
| Trương Đức Thái | Supervisor Owner | 2A202600328 |
| Đoàn Thư Ánh | Worker Owner | 2A202600364  |
| Đặng Phan Bảo Huy | MCP Owner | 2A202600461 |
| Mai Văn Quân |Trace & Docs Owner | 2A202600475 |

**Ngày nộp:** 2026-04-14  
**Repo:** https://github.com/Thaitd1102/Thaitd1102-Lab09-E403-Team63.git
**Độ dài khuyến nghị:** 600–1000 từ

---

## 1. Kiến trúc nhóm đã xây dựng (150–200 từ)

**Hệ thống tổng quan:**
Kiến trúc nhóm triển khai theo mô hình Supervisor-Worker thông qua StateGraph của LangGraph. Hệ thống có 1 Supervisor điều phối trung tâm và 3 workers chức năng: Retrieval Worker (truy xuất ChromaDB/Keyword), Policy Tool Worker (kiểm tra ngoại lệ và gọi API) và Synthesis Worker (tổng hợp LLM GPT-4o-mini). `AgentState` được truyền liên tục giữa các node, mang theo `retrieved_chunks`, `policy_result`, `worker_io_log` và lịch sử hành động để tiện traceback.

**Routing logic cốt lõi:**
Supervisor sử dụng Rule-based Keyword Matching để linh hoạt định tuyến. Nếu ở input (task) xuất hiện các chuỗi điều kiện như "hoàn tiền, refund, flash sale, cấp quyền, access", request được route ngay cho `policy_tool_worker`. Nếu không, task được đưa về luồng mặc định `retrieval_worker`. Mọi câu chứa "emergency, P1, 2am" sẽ kích hoạt cờ `risk_high`.

**MCP tools đã tích hợp:**
Hệ thống sử dụng plain function interface giả lập Real MCP. Trace (`run_20260414_152459.json`) cho thấy policy_tool đã kết nối hoàn chỉnh 3 công cụ:
- `get_ticket_info`: Truy vấn CSDL ảo trả về info ticket ưu tiên P1 (Ví dụ TK-001 lúc 2am).
- `search_kb`: Công cụ truy vấn ngữ nghĩa trong ChromaDB giúp Policy Tool lấy rule.
- `check_access_permission`: Rule engine MCP mô phỏng phân quyền nhân viên/contractor theo level và flag khẩn cấp.

---

## 2. Quyết định kỹ thuật quan trọng nhất (200–250 từ)

**Quyết định:** Áp dụng **Dual-mode Pattern (Tách biệt logic lõi và MCP Layer)**. Nhóm chọn thiết kế các functions như `search_kb` thành hai tầng: một bản plain call thông thường (`search_kb_fn`) phục vụ nội bộ và một bản wrapper `@mcp.tool()` dành cho external client; thay vì mix gọi thẳng ChromaDB bên trong Policy Tool.

**Bối cảnh vấn đề:**
Policy Tool cần truy xuất policy documents để suy luận logic hoàn tiền hoặc cấp quyền. Nếu đưa ChromaDB thẳng vào Worker, worker đó sẽ vi phạm tính độc lập (contract) và tạo "tight-coupling" với Database. Ngược lại, nếu thiết kế hoàn toàn qua HTTP FastMCP thì lại gây khó test và tăng latency ảo ở môi trường local.

**Các phương án đã cân nhắc:**

| Phương án | Ưu điểm | Nhược điểm |
|-----------|---------|-----------|
| Import client ChromaDB trực tiếp vào Policy Tool | Nhanh, ~0 overhead latency, code ngắn. | Tight-coupling. Vi phạm nghiêm trọng Contract thiết kế agent. |
| Chỉ xài Strict FastMCP `@tool` decorators | Đúng chuẩn Multi Agent System. | Gây lỗi `TypeError: Tool object is not callable` khi gọi qua Python code thường, test vất vả. |
| **Dual-Mode (Plain Func + Wrapper) và gọi qua `dispatch_tool()`** | Vừa chuẩn contract, loose-coupling, chạy mượt local, ghi log trace chuẩn MCP format. | Tốn thêm vài chục ms để thông qua dispatch layer; Maintain 2 hàm. |

**Phương án đã chọn và lý do:**
Nhóm ưu tiên tính Scalable và testability, quyết định chọn **Dual-mode API kết hợp Dispatch Tool interface**. `policy_tool` không đụng vào Storage (Chroma) mà bọc qua layer `dispatch_tool()`. Nhờ đó tool call nào cũng được ghi log timestamps và phân loại error kĩ lưỡng.

**Bằng chứng từ trace/code:**
Trong trace file của câu gq10, `mcp_tools_used` cho thấy call đã được log chi tiết qua `dispatch_tool`:
```json
"mcp_tools_used": [
  {
    "tool": "search_kb",
    "timestamp": "2026-04-14T15:24:59.1245",
    "output": [...]
  }
]
```

---

## 3. Kết quả grading questions (150–200 từ)

**Tổng điểm raw ước tính:** 96 / 96

**Câu pipeline xử lý tốt nhất:**
- ID: `gq03` và `gq10` — Lý do tốt: Exception detection hoạt động vượt kỳ vọng. Câu gq10 nhận diện xuất sắc `flash_sale_exception` từ cụm "đợt Flash Sale" và gán thẳng tín hiệu `policy_applies=False`, giúp LLM tổng hợp mượt mà và từ chối refund.

**Câu pipeline fail hoặc partial:**
- ID: `Q09` (Test 15 câu: ERR-403-AUTH là lỗi gì) — Fail ở đâu: Supervisor bị miss pattern matching (lowercase vs uppercase). Thay vì chuyển cho Human Review, nó đẩy tới Retrieval.  
  Root cause: Rule string đối chiếu của Supervisor thiếu `.lower()`. Khi test grading (`gq01-gq10`) thì không dính case này.

**Câu gq07 (abstain):** Nhóm xử lý thế nào?
Trả lời bằng confidence = 0.0 và output "Không tìm thấy thông tin". Model được tiêm System prompt grounded chặt chẽ (Answer ONLY from Provided Context), nên với một câu hỏi ma như phí phạt SLA, nó từ chối bịa số liệu.

**Câu gq09 (multi-hop khó nhất):** Trace ghi được 2 workers không? Kết quả thế nào?
Tuyệt vời! Trace ghi nhận trình tự: `Supervisor -> policy_tool_worker -> retrieval_worker -> synthesis_worker`. Tại vòng lặp `policy_tool`, worker đã hit trúng 3 MCP Tools một cách tuyến tính: `get_ticket_info(TK-001)` lấy data, `search_kb` nhận SLA rules, `check_access_permission` tra bypass. Kết quả thành công mỹ mãn.

---

## 4. So sánh Day 08 vs Day 09 — Điều nhóm quan sát được (150–200 từ)

**Metric thay đổi rõ nhất (có số liệu):**
Multi-hop cross-document accuracy tăng từ ~40% (Day 08) vọt lên **~73%** (Day 09). Điển hình ở câu gq09 (SLA P1 + Level 2 Access). Tuy nhiên Average Latency lại tăng đột ngột từ ~850ms (Day 08) lên trung bình **2,527ms** đo trên 15 queries. 

**Điều nhóm bất ngờ nhất khi chuyển từ single sang multi-agent:**
Debuggability (Khả năng rà lỗi) giảm hẳn 70% thời gian! Ở Day 08 Single agent, nếu sai phải dò toàn bộ codebase prompt + indexing. Với Day 09, object `AgentState` được truyền kèm `workers_called` và `route_reason` ở log trace giúp dễ dàng pinpoint việc lỗi sai do khâu lấy thiếu Data (vào Retrieval debug), hay do quyết định Route bị lệnh (vào Supervisor debug).

**Trường hợp multi-agent KHÔNG giúp ích hoặc làm chậm hệ thống:**
Truy vấn thông tin tra cứu tĩnh một tầng như `"SLA P1 là bao lâu?"`. Dùng LangGraph trong trường hợp này chỉ tạo thêm Overhead cho các hàm Graph Edge routing (tốn thêm gần 1s), trong khi một hàm Vector Search + LLM Prompt thông thường của Day 08 lại rẻ hơn rất nhiều và cho chung 1 kết quả.

---

## 5. Phân công và đánh giá nhóm (100–150 từ)

**Phân công thực tế:**

| Thành viên | Phần đã làm | Sprint |
|------------|-------------|--------|
| Trương Đức Thái | Supervisor Graph, Keyword Routing Engine | 1 |
| Đoàn Thư Ánh | Xây dựng 3 core Workers + Exception Logic | 2 |
| Đặng Phan Bảo Huy | Tích hợp MCP + Dispatch Interface | 3 |
| Mai Văn Quân | Generation file `eval_trace`, Grading Scripts & Report docs | 4 |


**Điều nhóm làm tốt:**
Module hoá tính năng cực kì xuất sắc. Mỗi function của Worker được viết độc lập với các `__name__ == "__main__"` để test riêng mà không phụ thuộc vào Orchestrator, nhờ đó tích hợp lên rất nhanh mà không có lỗi đứt luồng. 

**Điều nhóm làm chưa tốt hoặc gặp vấn đề về phối hợp:**
Thư viện LangGraph State thay đổi trạng thái liên tục trong runtime. Thiếu cơ chế validator check data-type ở mỗi Output của Worker dẫn đến một số tình trạng list comprehend crash ở lúc parse Synthesis Json. Giao diện debug chưa có.

**Nếu làm lại, nhóm sẽ thay đổi gì trong cách tổ chức?**
Tập trung mạnh hơn vào khâu "State Formatting Enforcement". Thêm Pydantic để Validate chặt chẽ dữ liệu mà Worker đưa vào State, bởi nếu một worker bị fail thầm lặng (VD trả array rỗng), chuỗi Agent Graph hoàn toàn không rõ nên Halt hay tiếp tục.

---

## 6. Nếu có thêm 1 ngày, nhóm sẽ làm gì? (50–100 từ)

Khắc phục vấn đề Latency bằng **Asynchronous Tools Execution** bên trong `policy_tool_worker`. Bằng chứng Trace cho câu gq09 cho thấy chuỗi I/O `get_ticket_info > search_kb > check_access_permission` chạy sync tuần tự mất lãng phí ~1.5 - 2s riêng của CPU. Thêm `asyncio.gather()` có thể dồn request về cùng một timeline gọi, có thể giảm được hơn 50% độ trễ cho các multi-hop phức tạp.

---
