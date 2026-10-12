"""
Demo-Safe LLM Scheduling Live Verification Script.
Runs against live Uvicorn backend on port 8000 using real Groq model openai/gpt-oss-120b.

Tests:
1. Quick Evaluation Live Test (mode='quick', verifies maximum 3 cases, minimal LLM calls, latency)
2. Tutor Live Test (measures latency, grounded answer, citations)
3. Assessment Live Test count=1 (measures latency, valid question generation)
4. Concurrent Evaluation + Tutor Test (Tutor receives priority and returns promptly without hanging)
"""

import time
import threading
import httpx

BASE_URL = "http://127.0.0.1:8000"
COURSE_ID = "a8797476-2729-4e5f-bd77-7330492c5015"


def test_1_quick_evaluation():
    print("\n" + "=" * 75, flush=True)
    print("1. QUICK EVALUATION LIVE TEST (mode='quick', bounded to max 3 cases)", flush=True)
    print("=" * 75, flush=True)
    client = httpx.Client(base_url=BASE_URL, timeout=60.0)

    t0 = time.time()
    # Trigger quick evaluation in sync mode or background
    res = client.post("/api/evaluation/run", json={
        "name": "Live Demo Quick Evaluation",
        "course_id": COURSE_ID,
        "mode": "quick",
        "sync": True
    })
    total_time = time.time() - t0

    print(f"Trigger Status: {res.status_code}", flush=True)
    data = res.json()
    eval_id = data.get("evaluation_id")
    print(f"Evaluation ID: {eval_id}", flush=True)
    print(f"Run Status: {data.get('status')}", flush=True)
    print(f"Total Evaluation Latency: {total_time:.2f}s", flush=True)

    results_res = client.get(f"/api/evaluation/{eval_id}/results")
    if results_res.status_code == 200:
        res_data = results_res.json()
        summary = res_data.get("summary", {})
        cases = res_data.get("results", [])
        print(f"Total Cases Executed: {len(cases)} (Expected <= 3 in quick mode)", flush=True)
        print(f"Passed Cases: {summary.get('passed_test_cases')}/{summary.get('total_test_cases')}", flush=True)
        print(f"Grounding Accuracy: {summary.get('grounding_accuracy')}", flush=True)
        print(f"Citation Accuracy: {summary.get('citation_accuracy')}", flush=True)
        print(f"Faithfulness: {summary.get('faithfulness')}", flush=True)
        print(f"Answer Relevancy: {summary.get('answer_relevancy')}", flush=True)
        for idx, c in enumerate(cases):
            print(f"  Case {idx+1} [{c.get('test_case_id')}]: Q='{c.get('question')[:45]}...' -> Grounded={c.get('actual_grounded')}, Passed={c.get('passed')}", flush=True)
        return total_time, res.status_code, len(cases), res_data
    else:
        status_res = client.get(f"/api/evaluation/{eval_id}")
        s_data = status_res.json()
        print(f"Evaluation Status Check: {s_data.get('status')}, Failure Reason: {s_data.get('failure_reason')}", flush=True)
        return total_time, res.status_code, 0, s_data


def test_2_live_tutor():
    print("\n" + "=" * 75, flush=True)
    print("2. LIVE TUTOR TEST (REAL GROQ: openai/gpt-oss-120b)", flush=True)
    print("=" * 75, flush=True)
    client = httpx.Client(base_url=BASE_URL, timeout=30.0)

    t0 = time.time()
    res = client.post("/api/tutor/chat", json={
        "course_id": COURSE_ID,
        "message": "What is Newton's first law of motion and how is inertia defined?"
    })
    latency = time.time() - t0
    print(f"Status: {res.status_code}", flush=True)
    print(f"Latency: {latency:.2f}s", flush=True)
    data = res.json()
    if res.status_code == 200:
        print(f"Grounded: {data.get('grounded')}", flush=True)
        print(f"Answer: {data.get('answer', '')[:200]}...", flush=True)
        sources = data.get("sources", [])
        print(f"Sources returned: {len(sources)}", flush=True)
    else:
        print(f"Error Response: {data}", flush=True)
    return latency, res.status_code, data


def test_3_live_assessment():
    print("\n" + "=" * 75, flush=True)
    print("3. LIVE ASSESSMENT COUNT=1 TEST (REAL GROQ: openai/gpt-oss-120b)", flush=True)
    print("=" * 75, flush=True)
    client = httpx.Client(base_url=BASE_URL, timeout=30.0)

    t0 = time.time()
    res = client.post("/api/assessments/generate", json={
        "course_id": COURSE_ID,
        "topic": "Newton's Laws of Motion",
        "question_type": "mcq",
        "count": 1,
        "difficulty": "medium"
    })
    latency = time.time() - t0
    print(f"Status: {res.status_code}", flush=True)
    print(f"Latency: {latency:.2f}s", flush=True)
    data = res.json()
    if res.status_code == 201:
        qs = data.get("questions", [])
        print(f"Questions Generated: {len(qs)}", flush=True)
        if qs:
            print(f"Question: {qs[0].get('question_text')[:100]}...", flush=True)
            print(f"Options: {qs[0].get('options')}", flush=True)
            print(f"Correct Answer: {qs[0].get('correct_answer')}", flush=True)
    else:
        print(f"Error Response: {data}", flush=True)
    return latency, res.status_code, data


def test_4_concurrent_eval_and_tutor():
    print("\n" + "=" * 75, flush=True)
    print("4. CONCURRENT EVALUATION + TUTOR TEST (PRIORITY VERIFICATION)", flush=True)
    print("=" * 75, flush=True)
    client = httpx.Client(base_url=BASE_URL, timeout=35.0)

    eval_result = {}
    tutor_result = {}

    def run_eval():
        try:
            t0 = time.time()
            r = client.post("/api/evaluation/run", json={
                "name": "Background Concurrent Eval",
                "course_id": COURSE_ID,
                "mode": "quick",
                "sync": False  # Run in background
            })
            eval_result["launch_status"] = r.status_code
            eval_result["launch_data"] = r.json()
            eval_result["eval_id"] = r.json().get("evaluation_id")
            eval_result["launch_latency"] = time.time() - t0
        except Exception as e:
            eval_result["error"] = str(e)

    def run_tutor():
        try:
            # Short wait so eval job hits the gate first
            time.sleep(0.3)
            t0 = time.time()
            r = client.post("/api/tutor/chat", json={
                "course_id": COURSE_ID,
                "message": "What is Newton's third law of motion?"
            })
            tutor_result["latency"] = time.time() - t0
            tutor_result["status"] = r.status_code
            tutor_result["data"] = r.json()
        except Exception as e:
            tutor_result["error"] = str(e)

    t_eval = threading.Thread(target=run_eval)
    t_tutor = threading.Thread(target=run_tutor)

    t_eval.start()
    t_tutor.start()

    t_eval.join()
    t_tutor.join()

    print(f"Background Eval Launched: Status={eval_result.get('launch_status')}, ID={eval_result.get('eval_id')}", flush=True)
    print(f"Concurrent Tutor Request: Status={tutor_result.get('status')}, Latency={tutor_result.get('latency', 0):.2f}s", flush=True)
    if tutor_result.get("status") == 200:
        print(f"  Tutor Grounded: {tutor_result['data'].get('grounded')}", flush=True)
        print(f"  Tutor Answer: {tutor_result['data'].get('answer', '')[:120]}...", flush=True)
    else:
        print(f"  Tutor Response: {tutor_result.get('data')}", flush=True)

    # Poll background evaluation completion
    eval_id = eval_result.get("eval_id")
    if eval_id:
        poll_start = time.time()
        final_status = "running"
        while time.time() - poll_start < 25.0:
            time.sleep(1.0)
            st_res = client.get(f"/api/evaluation/{eval_id}")
            if st_res.status_code == 200:
                final_status = st_res.json().get("status")
                if final_status in ("completed", "failed"):
                    break
        print(f"Background Eval Final Status: {final_status} (after {time.time() - poll_start:.1f}s)", flush=True)


if __name__ == "__main__":
    t_eval_latency, t_eval_status, t_eval_cases, _ = test_1_quick_evaluation()
    time.sleep(2.5)  # Respect pacing interval
    t_tutor_latency, t_tutor_status, _ = test_2_live_tutor()
    time.sleep(2.5)  # Respect pacing interval
    t_asmt_latency, t_asmt_status, _ = test_3_live_assessment()
    time.sleep(2.5)  # Respect pacing interval
    test_4_concurrent_eval_and_tutor()
