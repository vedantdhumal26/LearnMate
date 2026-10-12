import httpx
import json

r = httpx.get('http://127.0.0.1:8000/api/evaluation/cce69474-68d3-45b2-9669-bee0b7ea6645/results', timeout=30.0)
data = r.json()
summary = data.get('summary', {})
failures = data.get('failures', [])
results = data.get('results', [])

print('=' * 80)
print('EVALUATION RESULTS:')
print(f"Total cases:       {summary.get('total_test_cases')}")
print(f"Passed cases:      {summary.get('passed_test_cases')}")
print(f"Failed cases:      {len(failures)}")
print(f"Faithfulness:      {summary.get('faithfulness')}")
print(f"Answer Relevancy:  {summary.get('answer_relevancy')}")
print(f"Context Precision: {summary.get('context_precision')}")
print(f"Context Recall:    {summary.get('context_recall')}")
print(f"Citation Accuracy: {summary.get('citation_accuracy')}")
print(f"Grounding Accuracy:{summary.get('grounding_accuracy')}")
print(f"Course Isolation Failures: {summary.get('course_isolation_failures')}")
print(f"Supported Questions Passed: {summary.get('supported_questions_passed')} / {summary.get('supported_questions_count')}")
print(f"Unsupported Questions Passed: {summary.get('unsupported_questions_passed')} / {summary.get('unsupported_questions_count')}")
print('=' * 80)

if failures:
    print('FAILURES:')
    for f in failures:
        print(f"  - [{f.get('test_case_id')}]: {f.get('failure_reason')}")
else:
    print('ALL 40 TEST CASES PASSED PERFECTLY!')

print('=' * 80)
print('YOUTUBE CASES BREAKDOWN:')
yt_passed = 0
yt_total = 0
for res in results:
    tc_id = res.get('test_case_id', '')
    if 'yt' in tc_id:
        yt_total += 1
        if res.get('passed'):
            yt_passed += 1
        print(f"  [{tc_id}] passed={res.get('passed')}, grounded={res.get('actual_grounded')}, cit_ok={res.get('citation_correct')}, prec={res.get('context_precision')}, rec={res.get('context_recall')}, faith={res.get('faithfulness_score')}, rel={res.get('relevance_score')}")

print(f"YouTube Total: {yt_passed} / {yt_total} passed")
