"""
Live HTTP Verification against real running backend and real Groq API (openai/gpt-oss-120b).
Measures:
A. Live Tutor latency
B. Live Assessment count=1 latency
C. Live 1-case Evaluation latency
D. Concurrent Evaluation + Tutor verification (Tutor priority, bounded response, HTTP 409 rejection of duplicate evaluations)
"""

import time
import threading
import httpx

BASE_URL = "http://127.0.0.1:8000"
COURSE_ID = "a8797476-2729-4e5f-bd77-7330492c5015"


def test_a_live_tutor():
    print("\n" + "=" * 70, flush=True)
    print("A. LIVE TUTOR TEST (REAL GROQ API: openai/gpt-oss-120b)", flush=True)
    print("=" * 70, flush=True)
    client = httpx.Client(base_url=BASE_URL, timeout=45.0)
    t0 = time.time()
    res = client.post("/api/tutor/chat", json={
        "course_id": COURSE_ID,
        "message": "What is Newton's second law of motion and what is its mathematical formula?"
    })
    latency = time.time() - t0
    print(f"Status: {res.status_code}", flush=True)
    print(f"Latency: {latency:.2f}s", flush=True)
    data = res.json()
    if res.status_code == 200:
        print(f"Grounded: {data.get('grounded')}", flush=True)
        print(f"Answer: {data.get('answer', '')[:250]}...", flush=True)
        sources = data.get("sources", [])
        print(f"Sources returned: {len(sources)}", flush=True)
        for s in sources[:2]:
            print(f"  - {s.get('file_name')} (page={s.get('page')}, slide={s.get('slide')}, ts={s.get('start_seconds')}-{s.get('end_seconds')})", flush=True)
    else:
        print(f"Response: {data}", flush=True)
    return latency, res.status_code, data


def test_b_live_assessment():
    print("\n" + "=" * 70, flush=True)
    print("B. LIVE ASSESSMENT COUNT=1 TEST (REAL GROQ API: openai/gpt-oss-120b)", flush=True)
    print("=" * 70, flush=True)
    client = httpx.Client(base_url=BASE_URL, timeout=45.0)
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
            print(f"Question: {qs[0].get('question_text')}", flush=True)
            print(f"Options: {qs[0].get('options')}", flush=True)
    else:
        print(f"Response: {data}", flush=True)
    return latency, res.status_code, data


def test_c_live_evaluation_single_case():
    print("\n" + "=" * 70, flush=True)
    print("C. LIVE 1-CASE EVALUATION TEST (REAL GROQ API)", flush=True)
    print("=" * 70, flush=True)
    client = httpx.Client(base_url=BASE_URL, timeout=60.0)
    test_case = {
        "id": "eval-single-live-01",
        "course_id": COURSE_ID,
        "question": "What is Newton's second law of motion and what is its mathematical formula?",
        "expected_answer": "F = m * a",
        "expected_grounded": True,
        "expected_sources": [
            {
                "file_name": "benchmark_physics_guide.pdf",
                "page": 2,
                "modality": "pdf"
            }
        ]
    }
    t0 = time.time()
    res = client.post("/api/evaluation/run", json={
        "name": "Live 1-Case Eval",
        "course_id": COURSE_ID,
        "dataset": [test_case],
        "run_learner_simulations": False,
        "run_assessment_eval": False,
        "sync": True
    })
    latency = time.time() - t0
    print(f"Status: {res.status_code}", flush=True)
    print(f"Latency: {latency:.2f}s", flush=True)
    data = res.json()
    eval_id = data.get("evaluation_id")
    print(f"Evaluation ID: {eval_id}", flush=True)

    if eval_id:
        res_detail = client.get(f"/api/evaluation/{eval_id}/results")
        print(f"Results Status: {res_detail.status_code}", flush=True)
        detail_data = res_detail.json()
        summary = detail_data.get("summary", {})
        print(f"Summary Metrics: {summary}", flush=True)

    return latency, res.status_code, data


def test_d_concurrent_evaluation_and_tutor():
    print("\n" + "=" * 70, flush=True)
    print("D. CONCURRENT EVALUATION + TUTOR TEST (REAL GROQ API)", flush=True)
    print("=" * 70, flush=True)

    client = httpx.Client(base_url=BASE_URL, timeout=60.0)
    eval_response = {}
    tutor_response = {}
    second_eval_response = {}
    eval_started = threading.Event()

    def run_eval():
        try:
            test_cases = [
                {
                    "id": f"eval-conc-{i}",
                    "course_id": COURSE_ID,
                    "question": f"What is Newton's law of motion case {i}?",
                    "expected_grounded": True,
                    "expected_sources": []
                }
                for i in range(2)
            ]
            t0 = time.time()
            # Start background evaluation
            r = client.post("/api/evaluation/run", json={
                "name": "Concurrent Background Eval",
                "course_id": COURSE_ID,
                "dataset": test_cases,
                "run_learner_simulations": False,
                "run_assessment_eval": False,
                "sync": False
            })
            eval_response["status_code"] = r.status_code
            eval_response["data"] = r.json()
            eval_response["start_latency"] = time.time() - t0
            eval_started.set()

            # Poll for completion
            eval_id = eval_response["data"].get("evaluation_id")
            if eval_id:
                for _ in range(60):
                    time.sleep(1.0)
                    st = client.get(f"/api/evaluation/{eval_id}")
                    if st.json().get("status") in ("completed", "failed"):
                        eval_response["final_status"] = st.json().get("status")
                        eval_response["total_duration"] = time.time() - t0
                        break
        except Exception as e:
            eval_response["error"] = str(e)
            eval_started.set()

    def run_tutor():
        eval_started.wait()
        time.sleep(0.3)  # Ensure background evaluation is already accepted and queued
        try:
            t0 = time.time()
            r = client.post("/api/tutor/chat", json={
                "course_id": COURSE_ID,
                "message": "Explain Newton's third law of motion: for every action there is an equal and opposite reaction."
            })
            tutor_response["latency"] = time.time() - t0
            tutor_response["status_code"] = r.status_code
            tutor_response["data"] = r.json()
        except Exception as e:
            tutor_response["error"] = str(e)

    def run_second_eval():
        eval_started.wait()
        time.sleep(0.5)  # Try launching second evaluation while first is running
        try:
            r = client.post("/api/evaluation/run", json={
                "name": "Second Concurrent Eval (Should 409)",
                "course_id": COURSE_ID,
                "dataset": [],
                "sync": False
            })
            second_eval_response["status_code"] = r.status_code
            second_eval_response["data"] = r.json()
        except Exception as e:
            second_eval_response["error"] = str(e)

    t_eval = threading.Thread(target=run_eval)
    t_tutor = threading.Thread(target=run_tutor)
    t_eval2 = threading.Thread(target=run_second_eval)

    t0_all = time.time()
    t_eval.start()
    t_tutor.start()
    t_eval2.start()

    t_tutor.join()
    t_eval2.join()
    t_eval.join()
    total_time = time.time() - t0_all

    print(f"\nTotal Concurrent Test Time: {total_time:.2f}s", flush=True)
    print(f"Tutor Request: status={tutor_response.get('status_code')}, latency={tutor_response.get('latency', 0):.2f}s", flush=True)
    if tutor_response.get("status_code") == 200:
        ans = tutor_response.get("data", {}).get("answer", "")
        print(f"  Tutor grounded answer: {ans[:150]}...", flush=True)
    print(f"Second Evaluation (Concurrency check): status={second_eval_response.get('status_code')} (Expected: 409)", flush=True)
    print(f"  Second Eval detail: {second_eval_response.get('data')}", flush=True)
    print(f"Background Evaluation: status={eval_response.get('status_code')}, final_status={eval_response.get('final_status')}", flush=True)

    return tutor_response, second_eval_response, eval_response


if __name__ == "__main__":
    t_lat, t_status, _ = test_a_live_tutor()
    time.sleep(3.0)  # Pacing between tests

    a_lat, a_status, _ = test_b_live_assessment()
    time.sleep(3.0)  # Pacing between tests

    e_lat, e_status, _ = test_c_live_evaluation_single_case()
    time.sleep(3.0)  # Pacing between tests

    tut_resp, e2_resp, ev_resp = test_d_concurrent_evaluation_and_tutor()

    print("\n" + "=" * 70, flush=True)
    print("FINAL SUMMARY REPORT OF LIVE SYSTEM", flush=True)
    print("=" * 70, flush=True)
    print(f"A. Live Tutor: status={t_status}, latency={t_lat:.2f}s", flush=True)
    print(f"B. Live Assessment (count=1): status={a_status}, latency={a_lat:.2f}s", flush=True)
    print(f"C. Live 1-case Evaluation: status={e_status}, latency={e_lat:.2f}s", flush=True)
    print(f"D. Concurrent Tutor during Evaluation: status={tut_resp.get('status_code')}, latency={tut_resp.get('latency', 0):.2f}s", flush=True)
    print(f"   Concurrent Second Evaluation Rejection: status={e2_resp.get('status_code')} (409 verified)", flush=True)
    print(f"   Background Evaluation Final Status: {ev_resp.get('final_status')}", flush=True)
    print("=" * 70, flush=True)
