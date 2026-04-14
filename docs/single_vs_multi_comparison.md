# Single Agent vs Multi-Agent Comparison — Lab Day 09

**Nhóm:** 63
**Ngày:** 2026-04-14

> **Số liệu thực tế** từ trace của `eval_trace.py` (15 test questions) so với baseline Day 08 (single-agent RAG).

---

## 1. Metrics Comparison

| Metric | Day 08 (Single Agent) | Day 09 (Multi-Agent) | Delta | Ghi chú |
|--------|----------------------|---------------------|-------|---------|
| Avg confidence | ~0.78 | **0.87** | **+0.09** | Day 09 LLM được cung cấp evidence có cấu trúc hơn |
| Avg latency (ms) | ~850ms | **~2,100ms** | **+1,250ms** | +2 workers + MCP call overhead |
| Abstain rate (%) | ~7% | **13%** | **+6%** | Multi-agent abstain rõ hơn khi không có evidence |
| Multi-hop accuracy | ~40% | **73%** | **+33%** | Multi-hop được benefit từ policy_tool + retrieval route |
| Routing visibility | ✗ Không có | ✓ Có `route_reason` | N/A | Key advantage Day 09 |
| Debug time (estimate) | ~25 phút | **~8 phút** | **−17 phút** | Trace chỉ rõ worker nào sai |
| MCP tool calls | N/A | avg 1.2 calls/query | N/A | Chỉ cho policy queries |

> **Lưu ý:** Day 08 metrics là ước tính từ lab Day 08 với cùng bộ test questions. Day 09 metrics từ `artifacts/traces/` thực tế.

---

## 2. Phân tích theo loại câu hỏi

### 2.1 Câu hỏi đơn giản (single-document)

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Accuracy | ~85% | ~87% |
| Latency | ~850ms | ~1,800ms |
| Observation | Nhanh hơn, đủ cho simple lookups | Chậm hơn nhưng có trace để verify |

**Kết luận:** Multi-agent **không cải thiện đáng kể** với câu hỏi đơn giản single-doc. Đây là trade-off rõ ràng — latency tăng +1 giây mà accuracy chỉ tăng ~2%. Với câu đơn giản, single agent vẫn là lựa chọn tốt hơn về cost/performance.

### 2.2 Câu hỏi multi-hop (cross-document)

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Accuracy | ~40% | **~73%** |
| Routing visible? | ✗ | ✓ |
| Observation | Thường chỉ dùng 1 document dù cần 2 | policy_tool → retrieval → synthesis chain xử lý đúng multi-doc |

**Kết luận:** Multi-agent **cải thiện rõ rệt** (+33%) với multi-hop. Ví dụ điển hình: câu q15 (P1 lúc 2am + Level 2 access). Day 08 thường chỉ trả lời được 1 trong 2 phần (SLA hoặc access control), trong khi Day 09 kết hợp cả hai thông qua policy_tool worker gọi `check_access_permission` + retrieval worker lấy SLA chunks.

### 2.3 Câu hỏi cần abstain

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Abstain rate | ~7% | **~13%** |
| Hallucination cases | ~2 trường hợp | **0 trường hợp** |
| Observation | Single agent đôi khi bịa con số hoành tiền | Synthesis worker có grounded prompt nghiêm ngặt |

**Kết luận:** Multi-agent **tốt hơn đáng kể** trong việc abstain. Câu hỏi gq07 (mức phạt tài chính SLA P1 — không có trong docs) được hệ thống trả lời abstain đúng ("không có thông tin về mức phạt tài chính") thay vì bịa con số như Day 08.

---

## 3. Debuggability Analysis

### Day 08 — Debug workflow
```
Khi answer sai → phải đọc toàn bộ RAG pipeline code → tìm lỗi ở indexing/retrieval/generation
Không có trace → không biết bắt đầu từ đâu
Thời gian ước tính: ~25 phút
```

### Day 09 — Debug workflow
```
Khi answer sai → đọc trace → xem supervisor_route + route_reason
  → Nếu route sai → sửa supervisor routing logic
  → Nếu retrieval sai → test retrieval_worker độc lập
  → Nếu synthesis sai → test synthesis_worker độc lập
Thời gian ước tính: ~8 phút
```

**Câu cụ thể đã debug trong lab:** Câu q09 (ERR-403-AUTH) — supervisor route sang `retrieval_worker` thay vì `human_review`. Nhờ trace ghi `route_reason: "Defaulting to informational retrieval"`, phát hiện ngay rằng pattern `err-` không match `ERR-` uppercase. Fix: normalize `task.lower()` trước pattern check. Debug time: **3 phút** thay vì phải đọc lại toàn bộ codebase như Day 08.

---

## 4. Extensibility Analysis

| Scenario | Day 08 | Day 09 |
|---------|--------|--------|
| Thêm 1 tool/API mới | Phải sửa toàn prompt + re-test toàn flow | Thêm function vào `mcp_server.py` + 1 dòng dispatch |
| Thêm 1 domain mới | Phải retrain/re-prompt | Thêm 1 worker mới + routing rule |
| Thay đổi retrieval strategy | Sửa trực tiếp trong pipeline | Sửa `retrieval.py` độc lập, không ảnh hưởng supervisor |
| A/B test một phần | Khó — phải clone toàn pipeline | Dễ — swap worker, giữ supervisor + trace |

**Nhận xét:** Ví dụ thực tế: Để thêm `check_access_permission` vào hệ thống Day 08, cần thêm vào system prompt và re-test toàn bộ. Với Day 09, chỉ cần thêm function vào `mcp_server.py` và 3 dòng trong `policy_tool.py` — không chạm gì đến supervisor hay synthesis.

---

## 5. Cost & Latency Trade-off

| Scenario | Day 08 calls | Day 09 calls |
|---------|-------------|-------------|
| Simple query (SLA lookup) | 1 LLM call | 1 LLM call (synthesis only) |
| Policy query (refund) | 1 LLM call | 1 LLM call + 1–2 MCP calls |
| Multi-hop query (SLA + Access) | 1 LLM call | 1 LLM call + 2–3 MCP calls |
| MCP tool call | N/A | avg 1.2 per policy query |

**Nhận xét về cost-benefit:** Day 09 tốn thêm latency nhưng không tốn thêm LLM tokens đáng kể — MCP tools là plain function calls (không gọi LLM). Chi phí thực sự tăng là compute time của embedding + ChromaDB query (~200ms/call). Với production, có thể cache MCP results để giảm latency ~40%.

---

## 6. Kết luận

> **Multi-agent tốt hơn single agent ở điểm nào?**

1. **Multi-hop accuracy (+33%):** Supervisor-worker cho phép chain nhiều workers, mỗi worker chuyên sâu → cross-document reasoning tốt hơn đáng kể.
2. **Abstain & anti-hallucination:** Grounded prompt ở Synthesis worker + evidence từ Retrieval worker giúp hệ thống biết khi nào cần abstain (0 hallucination trong lab, so với 2 cases ở Day 08).
3. **Debuggability (−17 phút debug time):** `route_reason` + `workers_called` trong trace cho phép pinpoint lỗi mà không cần đọc toàn bộ codebase.

> **Multi-agent kém hơn hoặc không khác biệt ở điểm nào?**

1. **Latency (+1.25 giây):** Đây là trade-off chính. Multi-agent không phù hợp với use case cần response < 1 giây hoặc high-volume simple queries.

> **Khi nào KHÔNG nên dùng multi-agent?**

Không nên dùng multi-agent khi: (a) tất cả queries đều đơn giản, single-doc; (b) latency SLA nghiêm ngặt < 500ms; (c) hệ thống nhỏ 1-2 người maintain. Overhead của supervisor + routing chỉ có giá trị khi hệ thống đủ phức tạp để benefit từ specialization.

> **Nếu tiếp tục phát triển hệ thống, nhóm sẽ thêm gì?**

Implement **parallel worker execution**: với câu multi-hop như gq09, `retrieval_worker` và `policy_tool_worker` có thể chạy song song thay vì tuần tự — giảm ~40% latency cho multi-hop queries từ ~3,000ms xuống ~1,800ms. Trace của gq09 cho thấy 2 workers chạy tuần tự mất 2,940ms tổng.
