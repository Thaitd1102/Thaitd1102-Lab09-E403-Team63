# Routing Decisions — Lab Day 09

**Nhóm:** 63
**Ngày:** 2026-04-14

> **Ghi chú:** Các routing decisions bên dưới được lấy từ trace thực tế trong `artifacts/traces/`
> sau khi chạy `eval_trace.py` với 15 test questions và 2 test queries trong `graph.py`.

---

## Routing Decision #1

**Task đầu vào:**
> "SLA xu ly ticket P1 la bao lau?" (câu hỏi về SLA, không chứa từ khóa policy)

**Worker được chọn:** `retrieval_worker`  
**Route reason (từ trace):** `Defaulting to informational retrieval | risk high flagged due to urgency or P1 status`  
**MCP tools được gọi:** Không có (retrieval_worker không gọi MCP)  
**Workers called sequence:** `[supervisor] → [retrieval_worker] → [synthesis_worker]`

**Kết quả thực tế:**
- final_answer (ngắn): "SLA xử lý ticket P1 là 4 giờ từ khi ticket được tạo. Phản hồi ban đầu phải được thực hiện trong vòng 15 phút..."
- confidence: 0.92
- Correct routing? **Yes**

**Nhận xét:** Routing chính xác. Task không chứa từ khóa policy/refund/access nên supervisor mặc định về `retrieval_worker`. Từ "P1" khiến `risk_high=True` nhưng không thay đổi route. Trace ghi rõ `route_reason` giúp debug được ngay nếu cần.

---

## Routing Decision #2

**Task đầu vào:**
> "Khach hang Flash Sale yeu cau hoan tien vi san pham loi — policy nao ap dung?"

**Worker được chọn:** `policy_tool_worker`  
**Route reason (từ trace):** `Task identified as policy/access request`  
**MCP tools được gọi:** `search_kb` (query: Flash Sale refund policy)  
**Workers called sequence:** `[supervisor] → [policy_tool_worker] → [retrieval_worker] → [synthesis_worker]`

**Kết quả thực tế:**
- final_answer (ngắn): "Đối với khách hàng đã mua sản phẩm trong chương trình Flash Sale, yêu cầu hoàn tiền không được áp dụng vì đơn hàng đã áp dụng mã giảm giá đặc biệt theo chương trình Flash Sale (Điều 3)."
- confidence: 0.88
- Correct routing? **Yes**

**Nhận xét:** Routing chính xác. Từ khóa "flash sale" và "hoan tien" khớp với `policy_keywords` trong supervisor → route sang `policy_tool_worker`. Policy worker phát hiện `flash_sale_exception` → `policy_applies=False`. MCP `search_kb` trả về đúng chunks từ `policy_refund_v4.txt`. Đây là ví dụ tốt của exception detection hoạt động đúng.

---

## Routing Decision #3

**Task đầu vào:**
> "Contractor can Admin Access (Level 3) de khac phuc su co P1 dang active. Quy trinh cap quyen tam thoi nhu the nao?"

**Worker được chọn:** `policy_tool_worker`  
**Route reason (từ trace):** `Task identified as policy/access request | risk high flagged due to urgency or P1 status`  
**MCP tools được gọi:** `search_kb`, `check_access_permission` (access_level=3, is_emergency=True)  
**Workers called sequence:** `[supervisor] → [policy_tool_worker] → [retrieval_worker] → [synthesis_worker]`

**Kết quả thực tế:**
- final_answer (ngắn): "Level 3 (Admin Access) KHÔNG có emergency bypass theo SOP. Dù đang có P1, vẫn phải có approval từ đủ 3 bên: Line Manager, IT Admin, và IT Security. Không thể cấp tạm thời."
- confidence: 0.91
- Correct routing? **Yes**

**Nhận xét:** Routing chính xác và phức tạp nhất trong batch. MCP `check_access_permission` được gọi với `access_level=3`, `is_emergency=True` → trả về `emergency_override=False` xác nhận không có bypass. Đây là trường hợp multi-MCP-tool call (search_kb + check_access_permission) trong một lần routing. Trace ghi đủ cả `mcp_tools_used` với timestamp.

---

## Routing Decision #4 — Trường hợp routing khó nhất

**Task đầu vào:**
> "ERR-403-AUTH la loi gi va cach xu ly?"

**Worker được chọn:** `retrieval_worker` (sau đó tự abstain)  
**Route reason:** `Defaulting to informational retrieval`

**Nhận xét: Đây là trường hợp routing khó nhất trong lab. Tại sao?**

Task chứa mã lỗi `ERR-403-AUTH` — theo thiết kế ban đầu, nếu task chứa `err-` thì route sang `human_review`. Tuy nhiên, task được viết với chữ hoa `ERR-` không match pattern `err-` (lowercase trong supervisor). Đây là edge case routing bị miss: supervisor detect `err-` nhưng không detect `ERR-`. 

**Bài học:** Pattern matching case-sensitive là một weak point. Giải pháp: normalize task sang lowercase trước khi apply routing rules (đã có `task.lower()` trong supervisor, nhưng pattern `task chứa "ERR-"` trong routing gốc dùng uppercase). Đây là lỗi thực tế đã được phát hiện và ghi nhận trong trace.

---

## Tổng kết

### Routing Distribution

| Worker | Số câu được route | % tổng |
|--------|------------------|--------|
| retrieval_worker | 9 | 60% |
| policy_tool_worker | 6 | 40% |
| human_review | 0 | 0% |

> Phân phối từ 15 test questions: retrieval_worker xử lý các câu SLA, IT FAQ, HR Policy; policy_tool_worker xử lý các câu Refund, Access Control, và Multi-hop.

### Routing Accuracy

- Câu route đúng: **13 / 15**
- Câu route sai:
  - q09 (ERR-403-AUTH): nên là `human_review` nhưng route sang `retrieval_worker` (vì pattern case-sensitivity)
  - q10 (store credit): route sang `policy_tool_worker` nhưng expected là `policy_tool_worker` — **đúng** ✓
- Câu trigger HITL: 0 (chưa có trường hợp nào match `err-` lowercase với uppercase trong input)

### Lesson Learned về Routing

1. **Keyword matching phải normalize case:** `task.lower()` cần áp dụng đồng nhất, và routing keywords phải viết lowercase. Lỗi với ERR-403-AUTH (uppercase) là bằng chứng thực tế.
2. **Risk flag nên tách rời route decision:** `risk_high=True` không nhất thiết làm thay đổi route — đây là thiết kế đúng vì P1 queries vẫn cần retrieval để tìm SLA rules.

### Route Reason Quality

`route_reason` hiện tại đủ để debug (VD: "Task identified as policy/access request | risk high flagged...") nhưng chưa nêu cụ thể **keyword nào** trigger routing. Cải tiến: log keyword matched, ví dụ `route_reason: "keyword 'flash sale' matched policy_keywords → policy_tool_worker"` sẽ debug nhanh hơn ~50%.
