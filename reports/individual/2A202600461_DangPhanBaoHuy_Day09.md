# Báo Cá Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Đặng Phan Bảo Huy
**Vai trò trong nhóm:** MCP Owner  
**Ngày nộp:** 14/04/2026

## 1. Tôi phụ trách phần nào?

Trong Lab 09, tôi chịu trách nhiệm xây dựng Mock MCP Server (Sprint 3), đóng vai trò là "cầu nối tri thức" cho toàn bộ hệ thống Multi-Agent. Tôi không chỉ tạo ra dữ liệu giả lập mà còn tích hợp công cụ thực tế để Agent có thể tương tác với nguồn dữ liệu ngữ nghĩa.

- File chính: `mcp_server.py`
- Hàm tôi triển khai: `list_tools`, `dispatch_tool`, `tool_search_kb` (kết nối ChromaDB), `tool_get_ticket_info`, `tool_check_access_permission`, `tool_create_ticket`

Cách công việc của tôi kết nối với phần của thành viên khác:

- MCP Server cung cấp khả năng (capabilities) cho các Worker.
- Khi Supervisor chuyển task cho Retrieval Worker, Worker gọi `tool_search_kb` để lấy context.
- Nếu MCP trả về dữ liệu sai cấu trúc hoặc không kết nối được database, Worker sẽ không có căn cứ để trả lời, dẫn đến lỗi hoặc hallucination.

> Bằng chứng: `mcp_server.py` chứa định nghĩa `TOOL_SCHEMAS` chuẩn hóa theo giao thức Model Context Protocol.

## 2. Tôi đã ra một quyết định kỹ thuật gì?

Quyết định: chuyển `tool_search_kb` từ trả về text tĩnh sang truy vấn trực tiếp ChromaDB kế thừa từ Lab 08.

Lý do:

- Ban đầu tôi định mock dữ liệu để tiết kiệm thời gian.
- Bộ dữ liệu chính sách (SLA, Refund, Access Control) ở Lab 08 rất phong phú.
- Tôi đã copy thư mục `chroma_db` từ Lab 08 sang Lab 09 và viết logic kết nối, giúp hệ thống có khả năng Semantic Search thực thụ.

Các lựa chọn thay thế:

- Tạo một file JSON mới
- Dùng LLM để sinh dữ liệu ảo

Cả hai phương án đều thiếu tính thực tế và không tận dụng được dữ liệu sẵn có. Với `chromadb.PersistentClient(path='./chroma_db')`, tôi giúp Agent truy xuất đúng chunk dữ liệu cần thiết với độ chính xác cao.

Trade-off:

- Tôi chấp nhận rủi ro do khác tên collection giữa hai Lab (Lab 8 là `rag_lab`, Lab 9 code mẫu là `day09_docs`).
- Tôi chọn sửa code MCP để đọc đúng collection cũ thay vì re-index lại toàn bộ dữ liệu.

> Đoạn code minh họa:

```python
def tool_search_kb(query: str, top_k: int = 3) -> dict:
    # Quyết định: Kết nối DB thật thay vì mock text
    client = chromadb.PersistentClient(path='./chroma_db')
    collection = client.get_collection("rag_lab")  # Dùng lại data từ Lab 8
    results = collection.query(query_texts=[query], n_results=top_k)
    return {
        "chunks": results['documents'][0],
        "sources": [m.get('source') for m in results['metadatas'][0]],
        "total_found": len(results['documents'][0])
    }
```

## 3. Tôi đã sửa một lỗi gì?

Lỗi: `Collection 'day09_docs'` không tồn tại, dẫn đến `tool_search_kb` trả về mảng rỗng.

Symptom:

- Khi chạy `python mcp_server.py`, hệ thống cảnh báo: ⚠️ `Collection 'day09_docs' chưa có data`.
- Kết quả trả về: `{'chunks': [], 'sources': [], 'total_found': 0'}` kể cả khi thư mục `chroma_db` đã được copy đúng chỗ.

Root cause:

- Lab 8 khởi tạo database với tên collection `rag_lab`.
- Lab 9 code mẫu mặc định truy vấn `day09_docs`.
- Do tên collection không khớp, ChromaDB không tìm thấy dữ liệu.

Cách sửa:

- Kiểm tra tên collection trong thư mục `chroma_db`.
- Đổi truy vấn trong `tool_search_kb` từ `day09_docs` sang `rag_lab`.
- Thêm `try-except` để cảnh báo rõ ràng nếu thư mục database chưa được copy.

> Kết quả trước/sau:
>
> - Trước: `{'chunks': [], 'total_found': 0}`
> - Sau: `🔍 Test: search_kb -> [0.34] policy_sla.md: SLA cho ticket P1 là 4 giờ...`

## 4. Tôi tự đánh giá đóng góp của mình

Điểm mạnh:

- Tôi xây dựng `TOOL_SCHEMAS` rất chi tiết, giúp Worker không cần đoán input/output.
- Schema rõ ràng giúp giảm sai sót khi Worker gọi tool.
- Tôi cũng tích hợp FastAPI (option advanced) để nhóm có thể demo hệ thống dưới dạng web service.

Điểm yếu:

- `tool_create_ticket` hiện chỉ mock thông báo thành công.
- Chưa lưu ticket vào database hoặc file JSON, nên `get_ticket_info` chưa thể truy vấn lại ngay lập tức.
- Tính stateful của hệ thống chưa hoàn chỉnh.

Nhóm phụ thuộc vào tôi ở:

- toàn bộ logic nghiệp vụ kiểm tra quyền level 3,
- tra cứu mã lỗi IT,
- và quy trình trả lời khi người dùng hỏi về quyền truy cập.

Nếu tôi cung cấp sai quy trình, Agent có thể đưa ra tư vấn không chính xác.

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì?

Tôi sẽ cải tiến `tool_create_ticket` để lưu ticket thật vào một file SQLite nhỏ và duy trì trạng thái nhất quán.

- Mục tiêu: khi người dùng hỏi lại “Ticket của tôi trạng thái thế nào?”, hệ thống có thể trả lời đúng.
- Hiện tại MCP bị reset dữ liệu mỗi lần gọi, nên không thể trả lời được câu hỏi liên quan đến trạng thái ticket.
- Giải pháp: dùng SQLite để lưu ticket và đảm bảo hệ thống stateful.
