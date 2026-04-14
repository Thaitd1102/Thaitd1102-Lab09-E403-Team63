"""
workers/policy_tool.py — Policy & Tool Worker
Author: Worker Owner

Kiểm tra policy, xử lý exception cases (Flash Sale, digital product, temporal scoping),
và gọi MCP tools thông qua dispatch_tool() interface.
"""

import json
import re
from datetime import datetime

# Import MCP dispatch interface (plain callable, not FastMCP decorated)
try:
    from mcp_server import dispatch_tool, list_tools
except ImportError:
    def dispatch_tool(tool_name, **kwargs):
        return {"tool": tool_name, "input": kwargs, "output": {"error": "mcp_server not available"}, "timestamp": datetime.now().isoformat()}
    def list_tools():
        return []


# ─────────────────────────────────────────────
# Exception Patterns (Sprint 2 requirement)
# ─────────────────────────────────────────────
EXCEPTION_PATTERNS = {
    "flash_sale_exception": ["flash sale", "flashsale", "khuyến mãi đặc biệt"],
    "digital_product_exception": ["license key", "sản phẩm kỹ thuật số", "digital product", "subscription", "license"],
    "activated_product_exception": ["đã kích hoạt", "activated", "already activated"],
    "emergency_access": ["emergency", "khẩn cấp", "2am", "3am", "ngoài giờ"],
    "contractor_access": ["contractor", "nhà thầu", "thầu phụ"],
    "temporal_scoping": ["31/01", "01/02", "trước ngày", "before", "v3", "version 3"],
}


def _detect_exceptions(task: str) -> list:
    """Phát hiện exception cases trong task."""
    task_lower = task.lower()
    found = []
    for exc_type, keywords in EXCEPTION_PATTERNS.items():
        matched_keywords = [kw for kw in keywords if kw in task_lower]
        if matched_keywords:
            found.append({
                "type": exc_type,
                "matched_keywords": matched_keywords
            })
    return found


def run(state: dict) -> dict:
    """
    Policy Tool Worker — kiểm tra policy và exceptions, gọi MCP tools.

    Input: state với 'task', 'needs_tool', 'retrieved_chunks'
    Output: Updated state with policy_result, mcp_tools_used, worker_io_log
    """
    task = state.get("task", "")
    retrieved_chunks = state.get("retrieved_chunks", [])

    # Combine task and retrieved chunks for analysis
    combined_text = task + " " + " ".join([chunk.get("text", "") for chunk in retrieved_chunks])

    mcp_tools_used = []
    exceptions_found = _detect_exceptions(combined_text)
    policy_result = {
        "mcp_called": False,
        "exceptions_found": exceptions_found,
        "policy_applies": True,
        "source": [],
        "details": "",
        "policy_version_note": "",
    }

    # ── MCP Tool 1: get_ticket_info if ticket mentioned ──
    ticket_match = re.search(r'(TK-\d+)', task.upper())
    if "ticket" in task.lower() or ticket_match:
        ticket_id = ticket_match.group(1) if ticket_match else "TK-001"
        call = dispatch_tool("get_ticket_info", ticket_id=ticket_id)
        mcp_tools_used.append(call)
        policy_result["mcp_called"] = True
        policy_result["details"] += f"Ticket info: {json.dumps(call['output'], ensure_ascii=False)[:300]} | "

        # Log to state trace
        print(f"[policy_tool] MCP get_ticket_info({ticket_id}) → {str(call['output'])[:120]}")

    # ── MCP Tool 2: search_kb for policy/access queries ──
    if any(kw in combined_text.lower() for kw in ["hoàn tiền", "refund", "access", "cấp quyền", "level", "flash sale", "license"]):
        search_query = task[:200]  # use original task as query for max relevance
        call = dispatch_tool("search_kb", query=search_query, top_k=3)
        mcp_tools_used.append(call)
        policy_result["mcp_called"] = True
        chunks = call.get("output", [])
        if isinstance(chunks, list):
            for chunk in chunks:
                src = chunk.get("source", "")
                if src and src not in policy_result["source"]:
                    policy_result["source"].append(src)
            policy_result["details"] += f"KB search returned {len(chunks)} chunk(s). | "
        print(f"[policy_tool] MCP search_kb → {len(chunks) if isinstance(chunks, list) else 0} chunks")

    # ── MCP Tool 3: check_access_permission if access level mentioned ──
    if any(kw in combined_text.lower() for kw in ["level 2", "level 3", "level2", "level3", "admin access", "elevated access"]):
        # Detect level
        level = 3 if any(x in combined_text.lower() for x in ["level 3", "level3", "admin access", "elevated"]) else 2
        is_emergency = any(kw in combined_text.lower() for kw in ["p1", "emergency", "khẩn cấp", "2am"])
        requester_role = "contractor" if any(kw in combined_text.lower() for kw in ["contractor", "nhà thầu"]) else "employee"
        call = dispatch_tool("check_access_permission",
                             access_level=level,
                             requester_role=requester_role,
                             is_emergency=is_emergency)
        mcp_tools_used.append(call)
        policy_result["mcp_called"] = True
        policy_result["details"] += f"Access rule: {json.dumps(call['output'], ensure_ascii=False)[:300]} | "
        print(f"[policy_tool] MCP check_access_permission(level={level}, emergency={is_emergency})")

    # ── Handle Exception Cases ──
    for exc in exceptions_found:
        if exc["type"] == "flash_sale_exception":
            policy_result["policy_applies"] = False
            policy_result["details"] += "Flash Sale exception detected: standard refund policy does NOT apply. | "
        elif exc["type"] == "digital_product_exception":
            policy_result["policy_applies"] = False
            policy_result["details"] += "Digital product exception: license keys/subscriptions are non-refundable per policy_refund_v4.txt Clause 3. | "
        elif exc["type"] == "temporal_scoping":
            policy_result["policy_version_note"] = "Possible temporal scoping issue: order may pre-date refund policy v4 effective date (2026-02-01). Check policy v3."
            policy_result["details"] += "Temporal scoping: policy version may not apply. | "

    # Link retrieved chunks to policy decision
    for chunk in retrieved_chunks:
        chunk_id = chunk.get("id", "unknown")
        chunk_text = chunk.get("text", "")
        if any(exc["type"] in chunk_text for exc in exceptions_found):
            policy_result["details"] += f"Cited chunk {chunk_id}: {chunk_text[:100]}... | "

    worker_io_log = {
        "worker": "policy_tool_worker",
        "input_task": task,
        "retrieved_chunks_count": len(retrieved_chunks),
        "policy_decision_summary": policy_result["details"],
        "evidence_used": policy_result["source"],
        "mcp_tools_called": [c["tool"] for c in mcp_tools_used],
        "exceptions_detected": [e["type"] for e in exceptions_found],
        "timestamp": datetime.now().isoformat()
    }

    # Write results back to state
    state["policy_result"] = policy_result
    state["worker_io_log"] = worker_io_log

    return state


if __name__ == "__main__":
    # Independent test — Sprint 2 requirement
    import sys, io
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    print("=== Policy Tool Worker — Independent Test ===\n")

    test_cases = [
        {"task": "Khách hàng Flash Sale yêu cầu hoàn tiền vì sản phẩm lỗi — policy nào áp dụng?"},
        {"task": "Contractor cần Admin Access Level 3 để sửa P1 khẩn cấp lúc 2am"},
        {"task": "Ticket TK-001 — ai nhận thông báo đầu tiên?"},
    ]

    for tc in test_cases:
        print(f"Task: {tc['task'][:80]}")
        res = run(tc)
        print(f"  → mcp_called: {res['policy_result']['mcp_called']}")
        print(f"  → exceptions: {[e['type'] for e in res['policy_result']['exceptions_found']]}")
        print(f"  → mcp_tools: {[c['tool'] for c in res['mcp_tools_used']]}")
        print()
