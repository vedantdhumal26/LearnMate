import os
import sys
import json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import SessionLocal
from app.models.evaluation import EvaluationRun, EvaluationResult
from app.models.course import Course
from app.models.source import Source
from app.models.document_chunk import DocumentChunk
from app.services.evaluation.fixtures import get_default_evaluation_dataset

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

db = SessionLocal()
run = db.query(EvaluationRun).filter(EvaluationRun.id == "27f50037-c43a-40f9-a8ab-828471fe53c4").first()
results = db.query(EvaluationResult).filter(EvaluationResult.evaluation_run_id == run.id).all()
default_cases = {c.id: c for c in get_default_evaluation_dataset()}

print("=" * 80)
print("INSPECTION OF ALL 7 EVALUATION CASES (RUN ID: 27f50037-c43a-40f9-a8ab-828471fe53c4)")
print("=" * 80)
print("Run Created At:", run.created_at)
print("Run Summary Metrics:", run.summary_metrics)
print("=" * 80)

for idx, r in enumerate(results, 1):
    exp_c = default_cases.get(r.test_case_id)
    exp_sources = [s.model_dump() for s in exp_c.expected_sources] if exp_c else []
    sources = json.loads(r.retrieved_sources) if r.retrieved_sources else []
    retrieved_sids = list({s.get("source_id") for s in sources if s.get("source_id")})
    retrieved_modalities = list({s.get("modality") for s in sources if s.get("modality")})
    retrieved_locations = [
        f"page={s.get('page')}" if s.get('page') is not None
        else f"slide={s.get('slide')}" if s.get('slide') is not None
        else f"ts={s.get('start_seconds')}-{s.get('end_seconds')}" if s.get('start_seconds') is not None
        else "none"
        for s in sources
    ]

    print(f"\n{'='*30} CASE {idx}: {r.test_case_id} {'='*30}")
    print(f"question: {r.question}")
    print(f"expected_grounded: {r.expected_grounded}")
    print(f"actual_grounded: {r.actual_grounded}")
    print(f"retrieved_chunk_count: {len(sources)}")
    print(f"retrieved_source_ids: {retrieved_sids}")
    print(f"retrieved_modalities: {retrieved_modalities}")
    print(f"retrieved_locations: {retrieved_locations}")
    print(f"answer: {r.answer}")
    print(f"expected_source: {exp_sources}")
    print(f"citation_validator_result: {'PASS' if r.citation_correct else 'FAIL'}")
    print(f"faithfulness_result: {r.faithfulness_score}")
    print(f"relevancy_result: {r.relevance_score}")
    print(f"context_precision: {r.context_precision}")
    print(f"context_recall: {r.context_recall}")
    print(f"passed: {r.passed}")
    print(f"exact_failure_reason: {r.failure_reason}")

db.close()
