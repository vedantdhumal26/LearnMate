import os
import sys
import json
import time
import httpx

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE_URL = "http://127.0.0.1:8000"

def get_latest_benchmark_course_id():
    benchmark_file = os.path.join(os.path.dirname(__file__), "..", "app", "services", "evaluation", "benchmark_dataset_phase5b.json")
    if os.path.exists(benchmark_file):
        with open(benchmark_file, "r", encoding="utf-8") as f:
            cases = json.load(f)
            if cases and "course_id" in cases[0]:
                return cases[0]["course_id"]
    return "1bc65c6c-a273-46b4-810c-d1dab8317853"

def run_phase5b_eval():
    print("=" * 80)
    print("EXECUTING PHASE 5B 40-CASE COMPREHENSIVE SYSTEM EVALUATION")
    print("=" * 80)

    course_id = get_latest_benchmark_course_id()
    client = httpx.Client(base_url=BASE_URL, timeout=120.0)

    # 1. Health check
    h_res = client.get("/health")
    assert h_res.status_code == 200, f"Health check failed: {h_res.text}"

    # 2. Trigger Evaluation Run (Async via BackgroundTasks)
    print(f"\n[Step 1] Triggering POST /api/evaluation/run for Course {course_id}...")
    run_req = {
        "name": "Phase 5B 40-Case Comprehensive Multimodal Evaluation",
        "course_id": course_id,
        "sync": False,
        "run_learner_simulations": True,
        "run_assessment_eval": True
    }
    t0 = time.time()
    res = client.post("/api/evaluation/run", json=run_req)
    assert res.status_code == 201, f"Failed to start evaluation run: {res.text}"
    eval_id = res.json()["evaluation_id"]
    print(f"--> Evaluation run initiated: ID={eval_id}")

    # 3. Poll Status until completed
    print(f"\n[Step 2] Polling GET /api/evaluation/{eval_id} until completion...")
    st_data = None
    while True:
        st_res = client.get(f"/api/evaluation/{eval_id}")
        assert st_res.status_code == 200
        st_data = st_res.json()
        current_status = st_data["status"]
        elapsed = time.time() - t0
        print(f"  [{elapsed:.1f}s] Status: {current_status}...")
        if current_status in ["completed", "failed"]:
            break
        time.sleep(5.0)

    duration = time.time() - t0
    print(f"--> Evaluation finished in {duration:.1f}s with status: {st_data['status']}")
    print(f"--> Dataset Size: {st_data['dataset_size']}")
    print(f"--> Started At: {st_data['started_at']}")
    print(f"--> Completed At: {st_data['completed_at']}")
    assert st_data["status"] == "completed"

    # 4. Retrieve Detailed Results
    print(f"\n[Step 3] Retrieving full results from GET /api/evaluation/{eval_id}/results...")
    res_res = client.get(f"/api/evaluation/{eval_id}/results")
    assert res_res.status_code == 200
    res_data = res_res.json()
    summary = res_data["summary"]
    results = res_data["results"]
    learner_sims = res_data["learner_simulations"]
    failures = res_data["failures"]

    # 5. Print Metric Breakdown
    print("\n" + "=" * 80)
    print("LEARN SPHERE AI — PHASE 5B EVALUATION REPORT (ACTUAL MEASURED EXECUTION)")
    print("=" * 80)
    print(f"Evaluation Run ID: {eval_id}")
    print(f"Status:            {res_data['status'].upper()}")
    print(f"Total Test Cases:  {summary['total_test_cases']}")
    print(f"Passed Test Cases: {summary['passed_test_cases']} / {summary['total_test_cases']}")
    print(f"Failed Test Cases: {len(failures)} / {summary['total_test_cases']}")

    print("\nRAG METRICS:")
    print(f"  Answer Relevancy (Dense Cosine Similarity): {summary.get('answer_relevancy')}")
    print(f"  Faithfulness Score:                         {summary.get('faithfulness')}")
    print(f"  Context Precision:                          {summary.get('context_precision')}")
    print(f"  Context Recall:                             {summary.get('context_recall')}")

    print("\nGROUNDING & SAFETY:")
    print(f"  Grounding Accuracy:             {summary['grounding_accuracy'] * 100:.1f}%")
    print(f"  Supported Questions Answered:   {summary['supported_questions_passed']} / {summary['supported_questions_count']}")
    print(f"  Unsupported Questions Rejected: {summary['unsupported_questions_passed']} / {summary['unsupported_questions_count']}")
    print(f"  Course Isolation Failures:      {summary['course_isolation_failures']} / {summary['course_isolation_tests_count']}")

    print("\nCITATIONS:")
    print(f"  Citation Accuracy:              {summary['citation_accuracy'] * 100:.1f}%")
    print(f"  Citation Failure Count:         {summary['citation_failure_count']}")

    print("\nASSESSMENT QUALITY:")
    print(f"  Question Validity Rate:         {summary.get('assessment_valid_question_rate')}")
    print(f"  Duplicate Question Rate:        {summary.get('duplicate_rate')}")

    print("\nLEARNER PROFILES SIMULATION:")
    for sim in learner_sims:
        print(f"  [{sim['student_profile'].upper()}] Before: {sim['mastery_before']:.2f} -> After: {sim['mastery_after']:.2f} (Gain: {sim['mastery_gain']:+.2f}), Recs: {sim['recommendations_count']}, Weak: {sim['weak_topics_detected']}")

    if failures:
        print("\nFLAGGED FAILURES:")
        for idx, f in enumerate(failures, 1):
            print(f"  {idx}. [{f['test_case_id']}] {f['question']}")
            print(f"     Reason: {f['failure_reason']}")

    print("=" * 80)
    print("PHASE 5B EVALUATION RUN FINISHED!")
    print("=" * 80)
    return summary, failures

if __name__ == "__main__":
    run_phase5b_eval()
