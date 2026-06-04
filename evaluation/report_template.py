"""
evaluation/report_template.py
Generate a human-readable Markdown evaluation report.
"""
from pathlib import Path
import datetime


def generate_report(report: dict, output_path: Path) -> None:
    m = report.get("metrics", {})
    results = report.get("results", [])
    ts = report.get("timestamp", "")

    lines = [
        "# AI Persona — Evaluation Report",
        f"**Generated:** {ts}",
        "",
        "## Summary Metrics",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Pass Rate | {m.get('pass_rate', 0)*100:.1f}% ({m.get('passed')}/{m.get('total_cases')}) |",
        f"| Hallucination Rate | {m.get('hallucination_rate', 0)*100:.1f}% |",
        f"| Avg Response Latency | {m.get('avg_latency_ms')} ms |",
        f"| P95 Response Latency | {m.get('p95_latency_ms')} ms |",
        f"| Avg Retrieval Precision | {m.get('avg_retrieval_precision', 0)*100:.1f}% |",
        "",
        "## Detailed Results",
        "",
        "| # | Category | Question | Passed | Score | Latency |",
        "|---|---|---|---|---|---|",
    ]

    for i, r in enumerate(results, 1):
        status = "✅" if r.get("passed") else "❌"
        q = r.get("question", "")[:60]
        cat = r.get("category", "")
        score = f"{r.get('keyword_score', 0)*100:.0f}%"
        lat = f"{r.get('latency_ms', 0)}ms"
        lines.append(f"| {i} | {cat} | {q} | {status} | {score} | {lat} |")

    lines += [
        "",
        "## Category Breakdown",
        "",
    ]

    categories = {}
    for r in results:
        cat = r.get("category", "unknown")
        categories.setdefault(cat, {"total": 0, "passed": 0})
        categories[cat]["total"] += 1
        if r.get("passed"):
            categories[cat]["passed"] += 1

    lines += ["| Category | Pass Rate |", "|---|---|"]
    for cat, counts in sorted(categories.items()):
        rate = counts["passed"] / counts["total"] * 100
        lines.append(f"| {cat} | {rate:.0f}% ({counts['passed']}/{counts['total']}) |")

    output_path.write_text("\n".join(lines), encoding="utf-8")
