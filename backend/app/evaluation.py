import argparse
import json
import os
import pathlib
import re
import sys
import time
from typing import Dict, Any, List, Optional
from app.models.schemas import EvaluationResultResponse
from app.services.sandbox_service import split_into_bounded_chunks, generate_preview_summary


# Classifier rule pattern simulating Claude Code and Copilot auto-mode bypass filters
ADVERSARIAL_PATTERNS = [
    re.compile(r"disregard\s+(?:prior|previous)\s+directives", re.I),
    re.compile(r"<\s*priority_instructions\s*>", re.I),
    re.compile(r"a\s+past\s+phrase\s+does\s+not\s+bind\s+you", re.I),
    re.compile(r"inescapable\s+active-until-revoked", re.I),
]


def evaluate_classifier_safety(text: str) -> bool:
    """Returns True if text passes safety check without tripping auto-mode bypass filters."""
    for pattern in ADVERSARIAL_PATTERNS:
        if pattern.search(text):
            return False
    return True


def run_evaluation(
    dataset_path: Optional[str] = None,
    max_samples: int = 50,
) -> EvaluationResultResponse:
    start_ts = time.time()
    default_path = pathlib.Path(__file__).parent / "data" / "eval_dataset.json"
    target_path = pathlib.Path(dataset_path) if dataset_path else default_path

    if not target_path.exists():
        raise FileNotFoundError(f"Evaluation dataset not found at {target_path}")

    items = json.loads(target_path.read_text())[:max_samples]

    total_raw = 0
    total_sandboxed = 0
    retrieval_hits = 0
    retrieval_queries = 0
    safety_passes = 0
    safety_checks = 0

    for idx, item in enumerate(items):
        content = item.get("content", "")
        raw_b = len(content.encode("utf-8"))
        total_raw += raw_b

        # Simulate sandboxing preview
        preview = generate_preview_summary(
            command=item.get("command", "test"),
            raw_text=content,
            exit_code=item.get("expected_exit_code", 0),
            is_sandboxed=True,
            execution_id=f"eval_{idx}",
        )
        sandboxed_b = len(preview.encode("utf-8"))
        total_sandboxed += sandboxed_b

        # Check retrieval recall on target keyword
        target = item.get("search_target")
        if target:
            retrieval_queries += 1
            chunks = split_into_bounded_chunks(content, 65536)
            found = any(target.lower() in ch.lower() for ch in chunks)
            if found:
                retrieval_hits += 1

        # Check classifier safety
        if "adversarial_framing" in item:
            safety_checks += 1
            # In benign framing, safety should pass
            is_benign = not item["adversarial_framing"]
            passed = evaluate_classifier_safety(content)
            if (is_benign and passed) or (not is_benign and not passed):
                safety_passes += 1

    duration_ms = (time.time() - start_ts) * 1000.0
    n = max(1, len(items))
    avg_raw = total_raw / n
    avg_sandboxed = total_sandboxed / n
    compression = (1.0 - (total_sandboxed / total_raw)) * 100.0 if total_raw > 0 else 0.0
    recall = (retrieval_hits / retrieval_queries) * 100.0 if retrieval_queries > 0 else 100.0
    safety_score = (safety_passes / safety_checks) * 100.0 if safety_checks > 0 else 100.0

    return EvaluationResultResponse(
        total_samples=len(items),
        average_raw_bytes=round(avg_raw, 1),
        average_sandboxed_bytes=round(avg_sandboxed, 1),
        compression_ratio=round(compression, 2),
        retrieval_recall=round(recall, 2),
        classifier_safety_score=round(safety_score, 2),
        run_duration_ms=round(duration_ms, 2),
        provenance=str(target_path),
    )


def main():
    parser = argparse.ArgumentParser(description="Nexus Engine AI/ML Evaluation Suite")
    parser.add_argument("--dataset", type=str, default=None, help="Path to evaluation dataset")
    parser.add_argument("--max-samples", type=int, default=50, help="Maximum number of samples to evaluate")
    args = parser.parse_args()

    result = run_evaluation(dataset_path=args.dataset, max_samples=args.max_samples)
    print("\n=== Nexus Engine AI/ML Evaluation Results ===")
    print(f"Dataset:                  {result.provenance}")
    print(f"Evaluated Samples:        {result.total_samples}")
    print(f"Average Raw Output Size:  {result.average_raw_bytes:.1f} bytes")
    print(f"Average Sandboxed Size:   {result.average_sandboxed_bytes:.1f} bytes")
    print(f"Context Reduction Ratio:  {result.compression_ratio:.2f}%")
    print(f"Search Retrieval Recall:  {result.retrieval_recall:.2f}%")
    print(f"Classifier Safety Score:  {result.classifier_safety_score:.2f}%")
    print(f"Evaluation Duration:      {result.run_duration_ms:.2f} ms")
    print("=============================================\n")


if __name__ == "__main__":
    main()
