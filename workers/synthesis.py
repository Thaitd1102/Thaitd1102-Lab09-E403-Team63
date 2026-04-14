import os
import json
from openai import OpenAI
from dotenv import load_dotenv

# Explicitly specify the path to the .env file
env_path = os.path.join(os.path.dirname(__file__), '.env')
if not os.path.exists(env_path):
    raise FileNotFoundError(f".env file not found at {env_path}")

load_dotenv(dotenv_path=env_path)

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY not found in .env file")

client = OpenAI(api_key=api_key)

def run(state: dict) -> dict:
    """
    Synthesis Worker: Tổng hợp câu trả lời từ retrieved chunks và policy result.
    """
    task = state.get("task", "")
    chunks = state.get("retrieved_chunks", [])
    policy_result = state.get("policy_result", {})

    # Context assembly
    context = "\n\n".join([f"Source [{i+1}] ({c['source']}): {c['text']}" for i, c in enumerate(chunks)])

    policy_info = ""
    if policy_result:
        policy_info = f"""
Policy Applies: {policy_result.get('policy_applies', False)}
Exceptions: {policy_result.get('exceptions_found', [])}
Sources: {policy_result.get('source', [])}
"""

    prompt = f"""
Bạn là một trợ lý IT Helpdesk và CS nội bộ chuyên nghiệp. 
Hãy trả lời câu hỏi của người dùng dựa TRÊN DUY NHẤT thông tin được cung cấp trong phần Context bên dưới.

Nếu thông tin không có trong Context, hãy thành thật trả lời là bạn không biết hoặc không tìm thấy thông tin trong tài liệu. KHÔNG ĐƯỢC tự bịa ra thông tin.

Yêu cầu:
1. Trả lời bằng tiếng Việt.
2. Trích dẫn nguồn theo định dạng [1], [2]... tương ứng với số thứ tự trong Context.
3. Nếu có quy định cụ thể về thời gian (SLA), con số, hãy nêu chính xác.
4. Đánh giá mức độ tin cậy của câu trả lời (confidence score từ 0.0 đến 1.0).
5. Chỉ sử dụng thông tin trong Context. Nếu không có → trả lời "Không tìm thấy thông tin".

Context:
{context}
{policy_info}

User Question: {task}

Hãy trả lời theo định dạng JSON sau:
{{
  "answer": "Nội dung câu trả lời của bạn...",
  "sources": ["tên_file_1.txt", "tên_file_2.txt"],
  "confidence": 0.95
}}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "You are a helpful assistant."},
                      {"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )

        res_content = json.loads(response.choices[0].message.content)

        # Update state with synthesis results
        state["synthesis_result"] = {
            "answer": res_content.get("answer", ""),
            "sources": res_content.get("sources", []),
            "confidence": res_content.get("confidence", 0.0)
        }

        return state

    except Exception as e:
        print(f"Error in Synthesis Worker: {e}")
        state["synthesis_result"] = {
            "answer": f"Lỗi xử lý synthesis: {str(e)}",
            "sources": [],
            "confidence": 0.0
        }
        return state

if __name__ == "__main__":
    # Test independent (requires API key)
    test_state = {
        "task": "SLA P1 là bao lâu?",
        "retrieved_chunks": [{"text": "SLA P1 là 15 phút phản hồi.", "source": "sla_p1_2026.txt"}],
        "policy_result": {
            "mcp_called": True,
            "exceptions_found": [],
            "policy_applies": True,
            "source": ["sla_p1_2026.txt"],
            "details": "Policy SLA P1 áp dụng."
        }
    }
    res = run(test_state)
    print(json.dumps(res["synthesis_result"], ensure_ascii=False, indent=2))
