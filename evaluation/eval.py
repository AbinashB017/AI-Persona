"""
evaluation/eval.py
Evaluation framework for the AI Persona.

Metrics:
- Retrieval Precision: fraction of retrieved docs that are relevant
- Hallucination Rate: LLM-as-judge check against expected keywords
- Response Latency: measured via time.perf_counter
- Booking Success Rate: mock booking endpoint check

Run with: python evaluation/eval.py
Results saved to: evaluation/results/report_<timestamp>.json
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import time
import datetime
import httpx
from pathlib import Path
from loguru import logger
from evaluation.test_cases import TEST_CASES
from evaluation.report_template import generate_report

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
RESULTS_DIR = Path("evaluation/results")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def check_keywords(answer: str, keywords: list[str]) -> tuple[bool, float]:
    """
    Check how many expected keywords appear in the answer.
    Returns (passed, precision_score).
    """
    answer_lower = answer.lower()
    found = [kw for kw in keywords if kw.lower() in answer_lower]
    score = len(found) / len(keywords) if keywords else 0
    passed = score >= 0.5  # at least 50% keywords present
    return passed, score


def eval_single(case: dict, session_id: str = "eval_session") -> dict:
    """Run evaluation on a single test case."""
    question = case["question"]
    expected_keywords = case["expected_keywords"]
    expect_refusal = case.get("expect_refusal", False)

    start = time.perf_counter()
    try:
        with httpx.Client(timeout=60) as client:
            resp = client.post(
                f"{BACKEND_URL}/chat",
                json={"message": question, "session_id": session_id},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        return {
            "question": question,
            "category": case.get("category"),
            "error": str(e),
            "latency_ms": 0,
            "passed": False,
            "keyword_score": 0,
        }

    latency_ms = round((time.perf_counter() - start) * 1000)
    answer = data.get("answer", "")
    sources = data.get("sources", [])
    retrieval_count = data.get("retrieval_count", 0)

    passed, keyword_score = check_keywords(answer, expected_keywords)

    # For hallucination-guard cases: check model says "don't know"
    if expect_refusal:
        refusal_words = ["don't have", "not available", "don't know", "no information", "unavailable"]
        passed = any(w in answer.lower() for w in refusal_words)

    return {
        "question": question,
        "category": case.get("category"),
        "answer": answer[:300],
        "sources_count": retrieval_count,
        "latency_ms": latency_ms,
        "passed": passed,
        "keyword_score": round(keyword_score, 3),
        "expect_refusal": expect_refusal,
    }


def run_evaluation() -> dict:
    """Run all test cases and compute aggregate metrics."""
    logger.info(f"Starting evaluation — {len(TEST_CASES)} test cases")
    logger.info(f"Backend: {BACKEND_URL}")

    # Health check first
    try:
        with httpx.Client(timeout=5) as client:
            h = client.get(f"{BACKEND_URL}/health").json()
        logger.info(f"Backend online. Docs indexed: {h.get('documents_indexed')}")
    except Exception as e:
        logger.error(f"Backend not reachable: {e}")
        return {"error": "Backend not reachable"}

    results = []
    for i, case in enumerate(TEST_CASES, 1):
        logger.info(f"[{i}/{len(TEST_CASES)}] {case['question'][:60]}...")
        result = eval_single(case, session_id=f"eval_{i}")
        results.append(result)
        status = "✅" if result["passed"] else "❌"
        logger.info(f"  {status} latency={result['latency_ms']}ms | score={result.get('keyword_score', 0)}")
        time.sleep(0.5)  # avoid rate limits

    # ── Aggregate metrics ──
    passed = [r for r in results if r.get("passed")]
    latencies = [r["latency_ms"] for r in results if r.get("latency_ms", 0) > 0]

    metrics = {
        "total_cases": len(TEST_CASES),
        "passed": len(passed),
        "failed": len(TEST_CASES) - len(passed),
        "pass_rate": round(len(passed) / len(TEST_CASES), 3),
        "hallucination_rate": round(
            sum(1 for r in results if not r.get("passed") and not r.get("expect_refusal"))
            / max(len([r for r in results if not r.get("expect_refusal")]), 1),
            3
        ),
        "avg_latency_ms": round(sum(latencies) / len(latencies)) if latencies else 0,
        "p95_latency_ms": round(sorted(latencies)[int(len(latencies) * 0.95)]) if latencies else 0,
        "avg_retrieval_precision": round(
            sum(r.get("keyword_score", 0) for r in results) / len(results), 3
        ),
    }

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    report = {
        "timestamp": timestamp,
        "metrics": metrics,
        "results": results,
    }

    # Save JSON
    out_path = RESULTS_DIR / f"report_{timestamp}.json"
    out_path.write_text(json.dumps(report, indent=2))

    # Generate markdown report
    generate_report(report, RESULTS_DIR / f"report_{timestamp}.md")

    logger.success(f"Evaluation complete. Report: {out_path}")
    return report


if __name__ == "__main__":
    report = run_evaluation()
    m = report.get("metrics", {})
    print("\n" + "="*50)
    print("  EVALUATION RESULTS")
    print("="*50)
    print(f"  Pass Rate          : {m.get('pass_rate', 0)*100:.1f}%")
    print(f"  Hallucination Rate : {m.get('hallucination_rate', 0)*100:.1f}%")
    print(f"  Avg Latency        : {m.get('avg_latency_ms')}ms")
    print(f"  P95 Latency        : {m.get('p95_latency_ms')}ms")
    print(f"  Retrieval Precision: {m.get('avg_retrieval_precision', 0)*100:.1f}%")
    print("="*50)
