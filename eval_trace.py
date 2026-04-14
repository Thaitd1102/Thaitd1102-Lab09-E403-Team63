"""
eval_trace.py — Trace generation and evaluation
Sprint 4: Run test questions, save traces, and compare single vs multi.
"""

import json
import os
import time
from datetime import datetime
from graph import run_graph, save_trace

import sys
import io

# Fix Japanese/Vietnamese character encoding issues on Windows console
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Directory config
TRACE_DIR = "./artifacts/traces"
TEST_QUESTIONS_FILE = "./data/test_questions.json"
GRADING_QUESTIONS_FILE = "day09/lab/data/grading_questions.json"
GRADING_LOG_FILE = "./artifacts/grading_run.jsonl"

def run_evaluation(questions_file: str, output_dir: str):
    """
    Chạy pipeline với danh sách câu hỏi và lưu trace.
    """
    if not os.path.exists(questions_file):
        print(f"Error: {questions_file} not found.")
        return

    with open(questions_file, "r", encoding="utf-8") as f:
        questions = json.load(f)

    print(f"Starting evaluation of {len(questions)} questions...")
    
    results = []
    for i, q in enumerate(questions):
        question_text = q.get("question") or q.get("task")
        if not question_text:
            continue
            
        print(f"[{i+1}/{len(questions)}] Query: {question_text[:50]}...")
        
        try:
            result = run_graph(question_text)
            trace_file = save_trace(result, output_dir)
            results.append(result)
            print(f"   ✓ Done. Trace: {trace_file}")
        except Exception as e:
            print(f"   ✗ Error: {e}")

    return results

def analyze_traces(results):
    """
    Phân tích kết quả thực tế để điền vào docs.
    """
    total = len(results)
    if total == 0:
        return

    avg_latency = sum(r.get("latency_ms", 0) for r in results) / total
    avg_confidence = sum(r.get("confidence", 0) for r in results) / total
    
    routes = {}
    for r in results:
        route = r.get("supervisor_route", "unknown")
        routes[route] = routes.get(route, 0) + 1

    print("\n--- Evaluation Summary ---")
    print(f"Total Questions: {total}")
    print(f"Avg Latency: {avg_latency:.2f}ms")
    print(f"Avg Confidence: {avg_confidence:.2f}")
    print(f"Routing Distribution: {routes}")

def generate_grading_log():
    """
    Chạy grading questions và tạo file .jsonl theo yêu cầu SCORING.md.
    """
    if not os.path.exists(GRADING_QUESTIONS_FILE):
        print(f"\nError: {GRADING_QUESTIONS_FILE} not found.")
        return

    print("\n--- Running GRADING QUESTIONS ---")
    with open(GRADING_QUESTIONS_FILE, "r", encoding="utf-8") as f:
        questions = json.load(f)

    os.makedirs(os.path.dirname(GRADING_LOG_FILE), exist_ok=True)
    with open(GRADING_LOG_FILE, "w", encoding="utf-8") as out:
        for q in questions:
            print(f"Grading: {q['id']}")
            result = run_graph(q["question"])
            record = {
                "id": q["id"],
                "question": q["question"],
                "answer": result.get("final_answer"),
                "sources": result.get("sources", []),
                "supervisor_route": result.get("supervisor_route"),
                "route_reason": result.get("route_reason"),
                "workers_called": result.get("workers_called", []),
                "mcp_tools_used": result.get("mcp_tools_used", []),
                "confidence": result.get("confidence"),
                "hitl_triggered": result.get("hitl_triggered", False),
                "timestamp": datetime.now().isoformat(),
            }
            out.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Grading run complete. Log saved to {GRADING_LOG_FILE}")

if __name__ == "__main__":
    # 1. Run test questions
    results = run_evaluation(TEST_QUESTIONS_FILE, TRACE_DIR)
    
    # 2. Analyze
    if results:
        analyze_traces(results)
    
    # 3. Grading questions (if available)
    generate_grading_log()
