"""
graph.py — Supervisor + Workers Orchestration (Day 09 Sprint 1)
=====================================================================

Supervisor-Worker Pattern:
- AgentState: shared state across all nodes
- supervisor_node(): reads task, decides route
- route_decision(): keyword-based routing logic
- Graph structure: supervisor → [retrieval | policy_tool | synthesis] → END

Usage:
    python graph.py  # Run 2 test queries

Author: Trương Đức Thái (Supervisor Owner)
Date: 14/04/2026
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')

import json
import os
import time
from datetime import datetime
from typing import TypedDict, Literal, Optional, List, Dict
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Configuration
DEBUG = True

# ─────────────────────────────────────────────
# 1. Shared State — dữ liệu đi xuyên toàn graph
# ─────────────────────────────────────────────

class AgentState(TypedDict):
    """Shared state across all nodes in the graph."""
    
    # Input
    task: str                           # Câu hỏi đầu vào từ user

    # Supervisor decisions
    route_reason: str                   # Lý do route sang worker nào
    intent: str                         # Ý định của người dùng (refund, IT help, ...)
    entities: List[str]                 # Các thực thể quan trọng (flash_sale, defect, level_3, ...)
    risk_high: bool                     # True → cần HITL hoặc human_review
    needs_tool: bool                    # True → cần gọi external tool qua MCP
    hitl_triggered: bool                # True → đã pause cho human review

    # Worker outputs
    retrieved_chunks: list              # Output từ retrieval_worker
    retrieved_sources: list             # Danh sách nguồn tài liệu
    policy_result: dict                 # Output từ policy_tool_worker
    mcp_tools_used: list                # Danh sách MCP tools đã gọi

    # Final output
    final_answer: str                   # Câu trả lời tổng hợp
    sources: list                       # Sources được cite
    confidence: float                   # Mức độ tin cậy (0.0 - 1.0)

    # Trace & history
    history: list                       # Lịch sử các bước đã qua
    workers_called: list                # Danh sách workers đã được gọi
    supervisor_route: str               # Worker được chọn bởi supervisor
    latency_ms: Optional[int]           # Thời gian xử lý (ms)
    run_id: str                         # ID của run này
    worker_io_log: list                 # Log chi tiết từng worker call




def make_initial_state(task: str) -> AgentState:
    """Khởi tạo state cho một run mới."""
    return {
        "task": task,
        "route_reason": "",
        "intent": "",
        "entities": [],
        "risk_high": False,
        "needs_tool": False,
        "hitl_triggered": False,
        "retrieved_chunks": [],
        "retrieved_sources": [],
        "policy_result": {},
        "mcp_tools_used": [],
        "final_answer": "",
        "sources": [],
        "confidence": 0.0,
        "history": [],
        "workers_called": [],
        "supervisor_route": "",
        "latency_ms": None,
        "run_id": f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "worker_io_log": [],
    }


# ─────────────────────────────────────────────
# 2. Routing Logic
# ─────────────────────────────────────────────

def route_decision_logic(task: str) -> Dict:
    """
    LLM-based routing to analyze intent and entities.
    """
    prompt = f"""
    Analyze the user task for an IT Helpdesk & CS system.
    Goal: Decide which worker should handle this: 'policy_tool_worker' or 'retrieval_worker'.
    
    Rules:
    - If it's about refund, access permission, SLA policy, or complex rules -> policy_tool_worker.
    - If it's a general question about IT status, how-to, or FAQ -> retrieval_worker.
    - Extract intent (e.g., refund_request, access_request, sla_query).
    - Extract entities (e.g., flash_sale, defect, level_3, p1, ticket_id).
    - Mark risk_high=true if it mentions 'emergency', 'lỗi' (defect/error), or '2am/3am'.

    Task: {task}

    Return JSON:
    {{
        "route": "policy_tool_worker" | "retrieval_worker",
        "reason": "short explanation",
        "intent": "string",
        "entities": ["list", "of", "entities"],
        "risk_high": boolean
    }}
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "You are an intelligent supervisor router."},
                      {"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        decision = json.loads(response.choices[0].message.content)
        return decision
    except Exception as e:
        if DEBUG:
            print(f"LLM Routing failed: {e}. Falling back to keywords.")
        # Fallback to extremely basic logic if LLM fails
        return {
            "route": "policy_tool_worker" if any(kw in task.lower() for kw in ["hoàn tiền", "refund", "access"]) else "retrieval_worker",
            "reason": "Fallback due to LLM error",
            "intent": "unknown",
            "entities": [],
            "risk_high": "khẩn cấp" in task.lower()
        }



# ─────────────────────────────────────────────
# 3. Supervisor Node — quyết định route
# ─────────────────────────────────────────────

def supervisor_node(state: AgentState) -> AgentState:
    """
    Supervisor phân tích task và quyết định route thông qua LLM.
    """
    task = state["task"]
    
    if DEBUG:
        print(f"\n{'='*70}")
        print(f"🔍 SUPERVISOR_NODE (LLM)")
        print(f"{'='*70}")
        print(f"Task: {task}")
    
    # Route decision
    decision = route_decision_logic(task)
    route = decision.get("route", "retrieval_worker")
    route_reason = decision.get("reason", "")
    risk_high = decision.get("risk_high", False)
    
    # Log decision
    supervisor_log = {
        "node": "supervisor_node",
        "timestamp": datetime.now().isoformat(),
        "task": task,
        "route": route,
        "intent": decision.get("intent"),
        "entities": decision.get("entities"),
        "route_reason": route_reason,
        "risk_high": risk_high,
    }
    
    state["supervisor_route"] = route
    state["route_reason"] = route_reason
    state["intent"] = decision.get("intent", "")
    state["entities"] = decision.get("entities", [])
    state["risk_high"] = risk_high
    state["worker_io_log"].append(supervisor_log)
    state["history"].append(f"[supervisor] route={route}, intent={state['intent']}")
    
    if DEBUG:
        print(f"Route: {route}")
        print(f"Intent: {state['intent']}")
        print(f"Entities: {state['entities']}")
        print(f"Risk high: {risk_high}")
    
    return state


# ─────────────────────────────────────────────
# 4. Route Decision — conditional edge
# ─────────────────────────────────────────────

def route_decision(state: AgentState) -> Literal["retrieval_worker", "policy_tool_worker", "human_review"]:
    """
    Trả về tên worker tiếp theo dựa vào supervisor_route trong state.
    Đây là conditional edge của graph.
    """
    route = state.get("supervisor_route", "retrieval_worker")
    
    # Override to human_review nếu risk_high
    if state.get("risk_high") and "err-" in state["task"].lower():
        return "human_review"
    
    return route  # type: ignore



# ─────────────────────────────────────────────
# 5. Human Review Node — HITL placeholder
# ─────────────────────────────────────────────

def human_review_node(state: AgentState) -> AgentState:
    """
    HITL node: pause và chờ human approval.
    Trong lab này, implement dưới dạng placeholder (in ra warning).
    """
    if DEBUG:
        print(f"\n⚠️  HUMAN_REVIEW NODE")
    
    state["hitl_triggered"] = True
    state["workers_called"].append("human_review")
    
    log_entry = {
        "node": "human_review",
        "timestamp": datetime.now().isoformat(),
        "task": state["task"],
        "risk_reason": state.get("route_reason"),
        "status": "escalated - awaiting human input"
    }
    state["worker_io_log"].append(log_entry)
    state["history"].append("[human_review] HITL triggered")
    
    if DEBUG:
        print(f"   Task: {state['task']}")
        print(f"   Risk reason: {state.get('route_reason')}")
        print(f"   Action: Escalated to human (lab mode: auto-approved)\n")
    
    # Auto-approve để pipeline tiếp tục (lab mode)
    # Sau khi human approve, route về retrieval để lấy evidence
    state["supervisor_route"] = "retrieval_worker"
    
    return state


# ─────────────────────────────────────────────
# 6. Worker Nodes - Actual Implementation
# ─────────────────────────────────────────────

try:
    from workers.retrieval import run as retrieval_run
    from workers.policy_tool import run as policy_tool_run
    from workers.synthesis import run as synthesis_run
    RETRIEVAL_AVAILABLE = True
except Exception as e:
    if DEBUG:
        print(f"⚠️ Workers not available: {e}")
    RETRIEVAL_AVAILABLE = False


def retrieval_worker_node(state: AgentState) -> AgentState:
    """Retrieval Worker — finds relevant chunks from ChromaDB."""
    if DEBUG: print(f"\n📚 RETRIEVAL_WORKER")
    
    if RETRIEVAL_AVAILABLE:
        try:
            # Note: retrieval worker returns a dict, we need to update state
            res = retrieval_run(state)
            state.update(res)
            state["workers_called"].append("retrieval_worker")
        except Exception as e:
            if DEBUG: print(f"   Error: {e}")
    return state


def policy_tool_worker_node(state: AgentState) -> AgentState:
    """Policy Tool Worker — checks policies and MCP tools."""
    if DEBUG: print(f"\n⚖️  POLICY_TOOL_WORKER")
    
    if RETRIEVAL_AVAILABLE:
        try:
            state = policy_tool_run(state)
        except Exception as e:
            if DEBUG: print(f"   Error: {e}")
    return state


def synthesis_worker_node(state: AgentState) -> AgentState:
    """Synthesis Worker — synthesizes final answer with citations."""
    if DEBUG: print(f"\n🔗 SYNTHESIS_WORKER")
    
    if RETRIEVAL_AVAILABLE:
        try:
            state = synthesis_run(state)
            # synthesis worker returns result in state["synthesis_result"]
            if "synthesis_result" in state:
                sr = state["synthesis_result"]
                state["final_answer"] = sr.get("answer", "")
                state["sources"] = sr.get("sources", [])
                state["confidence"] = sr.get("confidence", 0.0)
        except Exception as e:
            if DEBUG: print(f"   Error: {e}")
    return state



# ─────────────────────────────────────────────
# 7. Build Graph
# ─────────────────────────────────────────────

def build_graph():
    """
    Xây dựng orchestrator: supervisor → route → workers → synthesis
    
    Implementation: Simple Python orchestrator (không cần LangGraph cho lab này)
    """
    
    def run_orchestration(state: AgentState) -> AgentState:
        """Main orchestration loop."""
        start_time = time.time()
        
        # Step 1: Supervisor decides route
        state = supervisor_node(state)
        
        # Step 2: Route to appropriate worker
        route = route_decision(state)
        
        if DEBUG:
            print(f"\nRouting to: {route}")
        
        if route == "human_review":
            state = human_review_node(state)
            # After human approval, continue with retrieval
            state = retrieval_worker_node(state)
        elif route == "policy_tool_worker":
            state = policy_tool_worker_node(state)
            # Policy worker may need retrieval context first for grounding
            if not state["retrieved_chunks"]:
                state = retrieval_worker_node(state)
        else:
            # Default: retrieval_worker
            state = retrieval_worker_node(state)
        
        # Step 3: Always synthesize
        state = synthesis_worker_node(state)
        
        # Calculate latency
        state["latency_ms"] = int((time.time() - start_time) * 1000)
        state["history"].append(f"[graph] completed in {state['latency_ms']}ms")
        
        return state
    
    return run_orchestration


# ─────────────────────────────────────────────
# 8. Public API
# ─────────────────────────────────────────────

_graph = build_graph()


def run_graph(task: str) -> AgentState:
    """
    Entry point: nhận câu hỏi, trả về AgentState với full trace.

    Args:
        task: Câu hỏi từ user

    Returns:
        AgentState với final_answer, trace, routing info, v.v.
    """
    state = make_initial_state(task)
    result = _graph(state)
    return result


# ─────────────────────────────────────────────
# 9. Test & Main
# ─────────────────────────────────────────────

def test_query(query: str):
    """Run a single query through the graph."""
    
    print(f"\n{'='*70}")
    print(f"🚀 QUERY: {query}")
    print(f"{'='*70}")
    
    result = run_graph(query)
    
    # Print results
    print(f"\n{'='*70}")
    print(f"📊 RESULTS")
    print(f"{'='*70}")
    print(f"Route reason: {result.get('route_reason')}")
    print(f"Risk high: {result.get('risk_high')}")
    print(f"Workers called: {result.get('workers_called')}")
    print(f"Final answer: {result.get('final_answer')[:150]}...")
    print(f"Confidence: {result.get('confidence')}")
    print(f"Latency: {result.get('latency_ms')}ms")
    
    print(f"\n📝 Worker IO Log:")
    for i, log in enumerate(result.get('worker_io_log', [])):
        print(f"  {i+1}. {log.get('node', '?')} @ {log.get('timestamp', '?')}")
    
    return result


def main():
    """Main entry point."""
    
    print("\n" + "="*70)
    print("🤖 LAB DAY 09 — GRAPH ORCHESTRATION (SPRINT 1)")
    print("="*70)
    print("Author: Trương Đức Thái (Supervisor Owner)")
    print("Date: 14/04/2026")
    
    # Ensure output directory
    os.makedirs("artifacts/traces", exist_ok=True)
    
    # Test queries
    test_queries = [
        "SLA ticket P1 là bao lâu?",  # Should route to retrieval_worker
        "Chính sách hoàn tiền cho Flash Sale là gì?",  # Should route to policy_tool_worker
    ]
    
    all_results = []
    for query in test_queries:
        result = test_query(query)
        all_results.append(result)
    
    # Summary
    print(f"\n{'='*70}")
    print(f"📈 SUMMARY")
    print(f"{'='*70}")
    print(f"Total queries: {len(test_queries)}")
    print(f"Queries completed: {len(all_results)}")
    
    # Save traces
    trace_file = f"artifacts/traces/supervisor_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
    
    with open(trace_file, 'w', encoding='utf-8') as f:
        for i, result in enumerate(all_results):
            trace_entry = {
                "query_id": i + 1,
                "task": result.get("task"),
                "route_reason": result.get("route_reason"),
                "risk_high": result.get("risk_high"),
                "workers_called": result.get("workers_called"),
                "final_answer": result.get("final_answer")[:200],
                "confidence": result.get("confidence"),
                "latency_ms": result.get("latency_ms"),
                "hitl_triggered": result.get("hitl_triggered"),
                "timestamp": datetime.now().isoformat(),
            }
            f.write(json.dumps(trace_entry, ensure_ascii=False) + "\n")
    
    print(f"\n✅ Trace saved: {trace_file}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()


def save_trace(state: AgentState, output_dir: str = "./artifacts/traces") -> str:
    """Lưu trace ra file JSON."""
    os.makedirs(output_dir, exist_ok=True)
    filename = f"{output_dir}/{state['run_id']}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    return filename


# ─────────────────────────────────────────────
# 8. Manual Test
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("Day 09 Lab — Supervisor-Worker Graph")
    print("=" * 60)

    test_queries = [
        "SLA xử lý ticket P1 là bao lâu?",
        "Khách hàng Flash Sale yêu cầu hoàn tiền vì sản phẩm lỗi — được không?",
        "Cần cấp quyền Level 3 để khắc phục P1 khẩn cấp. Quy trình là gì?",
    ]

    for query in test_queries:
        print(f"\n▶ Query: {query}")
        result = run_graph(query)
        print(f"  Route   : {result['supervisor_route']}")
        print(f"  Reason  : {result['route_reason']}")
        print(f"  Workers : {result['workers_called']}")
        print(f"  Answer  : {result['final_answer'][:100]}...")
        print(f"  Confidence: {result['confidence']}")
        print(f"  Latency : {result['latency_ms']}ms")

        # Lưu trace
        trace_file = save_trace(result)
        print(f"  Trace saved → {trace_file}")

    print("\n✅ graph.py test complete. Implement TODO sections in Sprint 1 & 2.")