"""
Evaluation harness: measures (1) extraction accuracy against hand-labeled
real emails, and (2) agent tool-selection accuracy against test questions
with a known-correct tool. Same practice as Mail Agent's 85%->90% workflow,
extended to also measure agentic decision quality - a step up from pure
classification accuracy.
"""

import json

from eval.eval_set import EVAL_SET
from eval.tool_eval_set import TOOL_EVAL_SET
from extraction.extractor import extract_order
from agent.loop import run_agent


def _compare_items(expected_items, actual_items):
    """Order-insensitive comparison of item lists by (name, quantity, price)."""
    if len(expected_items) != len(actual_items):
        return False

    def normalize(items):
        return sorted(
            (i["item_name"].strip().lower(), int(i["quantity"]), round(float(i["item_price"]), 2))
            for i in items
        )

    return normalize(expected_items) == normalize(actual_items)


def run_extraction_eval(verbose=True):
    results = []

    for case in EVAL_SET:
        parsed, error = extract_order(case["distilled_text"], reference_year=case["reference_year"])
        expected = case["expected"]

        if error:
            results.append({"id": case["id"], "pass": False, "reason": f"extraction failed: {error}"})
            if verbose:
                print(f"[FAIL] {case['id']} - extraction error: {error}")
            continue

        checks = {
            "restaurant": parsed.get("restaurant", "").strip().lower() == expected["restaurant"].strip().lower(),
            "order_date": parsed.get("order_date") == expected["order_date"],
            "total_amount": abs(float(parsed.get("total_amount", -1)) - expected["total_amount"]) < 0.01,
            "items": _compare_items(expected["items"], parsed.get("items", [])),
        }
        passed = all(checks.values())
        results.append({"id": case["id"], "pass": passed, "checks": checks})

        if verbose:
            status = "PASS" if passed else "FAIL"
            print(f"[{status}] {case['id']}")
            if not passed:
                failed_fields = [k for k, v in checks.items() if not v]
                print(f"   failed on: {failed_fields}")
                print(f"   expected:  {json.dumps(expected, default=str)}")
                print(f"   got:       {json.dumps(parsed, default=str)}")

    total = len(results)
    passed_count = sum(1 for r in results if r["pass"])
    accuracy = round(100 * passed_count / total, 1) if total else 0.0

    if verbose:
        print(f"\nExtraction accuracy: {passed_count}/{total} ({accuracy}%)")

    return {"total": total, "passed": passed_count, "accuracy_pct": accuracy, "results": results}


def run_tool_selection_eval(verbose=True):
    results = []

    for case in TOOL_EVAL_SET:
        answer, tools_called = run_agent(case["query"], verbose=False, return_trace=True)
        passed = case["expected_tool"] in tools_called

        results.append({
            "query": case["query"],
            "expected_tool": case["expected_tool"],
            "tools_called": tools_called,
            "pass": passed,
        })

        if verbose:
            status = "PASS" if passed else "FAIL"
            print(f"[{status}] {case['query']!r}")
            print(f"   expected: {case['expected_tool']} | got: {tools_called}")

    total = len(results)
    passed_count = sum(1 for r in results if r["pass"])
    accuracy = round(100 * passed_count / total, 1) if total else 0.0

    if verbose:
        print(f"\nTool-selection accuracy: {passed_count}/{total} ({accuracy}%)")

    return {"total": total, "passed": passed_count, "accuracy_pct": accuracy, "results": results}


if __name__ == "__main__":
    print("===== Extraction Accuracy =====")
    run_extraction_eval()
    print("\n===== Tool-Selection Accuracy =====")
    run_tool_selection_eval()
