"""
Manual Live Verification against Real Groq API (Step 14 & 15).
Runs real requests to measure:
A. Live Tutor latency
B. Live Assessment count=1 latency
C. Live 1-case Evaluation latency
D. Concurrent Evaluation + Tutor verification (Tutor must not hang, receives prompt response)
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(line_buffering=True, encoding="utf-8")
except Exception:
    pass
import time
import threading
from app.core.database import SessionLocal
from app.schemas.tutor import TutorChatRequest
from app.schemas.assessment import AssessmentGenerateRequest
from app.schemas.evaluation import EvaluationRunRequest, EvaluationTestCase, ExpectedSource
from app.services.rag.tutor_service import TutorService
from app.services.assessment.assessment_service import AssessmentService
from app.services.evaluation.evaluator import EvaluationEngine
from app.services.evaluation.eval_lock import get_evaluation_lock_manager
from app.core.logging_config import logger

COURSE_ID = "a8797476-2729-4e5f-bd77-7330492c5015"


def test_a_live_tutor():
    print("\n" + "=" * 60)
    print("A. LIVE TUTOR TEST (REAL GROQ API)")
    print("=" * 60)
    db = SessionLocal()
    try:
        tutor_service = TutorService()
        req = TutorChatRequest(
            course_id=COURSE_ID,
            message="What is Newton's second law of motion and what is its mathematical equation?"
        )
        t0 = time.time()
        resp = tutor_service.answer_question(request=req, db=db, request_type="tutor")
        latency = time.time() - t0
        print(f"Latency: {latency:.2f}s")
        print(f"Grounded: {resp.grounded}")
        print(f"Answer: {resp.answer[:200]}...")
        print(f"Sources: {len(resp.sources)}")
        for s in resp.sources[:2]:
            print(f"  - {s.file_name} (page={s.page}, slide={s.slide}, ts={s.start_seconds}-{s.end_seconds})")
        return latency, resp
    except Exception as e:
        print(f"Tutor error / 429: {e}")
        return None, str(e)
    finally:
        db.close()


def test_b_live_assessment():
    print("\n" + "=" * 60)
    print("B. LIVE ASSESSMENT COUNT=1 TEST (REAL GROQ API)")
    print("=" * 60)
    db = SessionLocal()
    try:
        service = AssessmentService()
        req = AssessmentGenerateRequest(
            course_id=COURSE_ID,
            topic="Newton's Laws",
            question_type="mcq",
            count=1,
            difficulty="medium"
        )
        t0 = time.time()
        resp = service.generate_assessment(db=db, request=req)
        latency = time.time() - t0
        print(f"Latency: {latency:.2f}s")
        print(f"Total Questions: {resp.total_questions}")
        if resp.questions:
            q = resp.questions[0]
            print(f"Question: {q.question_text}")
            print(f"Options: {q.options}")
        return latency, resp
    except Exception as e:
        print(f"Assessment error / 429: {e}")
        return None, str(e)
    finally:
        db.close()


def test_c_live_evaluation_single_case():
    print("\n" + "=" * 60)
    print("C. LIVE 1-CASE EVALUATION TEST (REAL GROQ API)")
    print("=" * 60)
    db = SessionLocal()
    try:
        lock_mgr = get_evaluation_lock_manager()
        lock_mgr.force_reset()
        engine = EvaluationEngine()

        test_case = EvaluationTestCase(
            id="eval-live-single",
            course_id=COURSE_ID,
            question="What is Newton's second law of motion and its mathematical equation?",
            expected_answer="F = m * a",
            expected_grounded=True,
            expected_sources=[
                ExpectedSource(
                    file_name="benchmark_physics_guide.pdf",
                    page=2,
                    modality="pdf"
                )
            ]
        )

        req = EvaluationRunRequest(
            name="Manual Live Single Case Eval",
            course_id=COURSE_ID,
            dataset=[test_case],
            run_learner_simulations=False,
            run_assessment_eval=False,
            sync=True
        )

        t0 = time.time()
        run = engine.run_evaluation(db=db, request=req)
        latency = time.time() - t0
        print(f"Latency: {latency:.2f}s")
        print(f"Status: {run.status}")
        print(f"Summary Metrics: {run.summary_metrics}")
        return latency, run
    except Exception as e:
        print(f"Evaluation error / 429: {e}")
        return None, str(e)
    finally:
        db.close()


def test_d_concurrent_evaluation_and_tutor():
    print("\n" + "=" * 60)
    print("D. CONCURRENT EVALUATION + TUTOR TEST (REAL GROQ API)")
    print("=" * 60)
    get_evaluation_lock_manager().force_reset()

    eval_result = {}
    tutor_result = {}
    eval_started = threading.Event()

    def run_eval():
        db = SessionLocal()
        try:
            engine = EvaluationEngine()
            test_cases = [
                EvaluationTestCase(
                    id=f"eval-conc-{i}",
                    course_id=COURSE_ID,
                    question=f"What is Newton's law case {i}?",
                    expected_grounded=True
                )
                for i in range(2)
            ]
            req = EvaluationRunRequest(
                name="Concurrent Live Eval",
                course_id=COURSE_ID,
                dataset=test_cases,
                run_learner_simulations=False,
                run_assessment_eval=False,
                sync=True
            )
            eval_started.set()
            t0 = time.time()
            run = engine.run_evaluation(db=db, request=req)
            eval_result["latency"] = time.time() - t0
            eval_result["status"] = run.status
        except Exception as e:
            eval_result["error"] = str(e)
        finally:
            db.close()

    def run_tutor():
        eval_started.wait()
        time.sleep(0.2)  # Ensure evaluation is actively queued/running
        db = SessionLocal()
        try:
            tutor_service = TutorService()
            req = TutorChatRequest(
                course_id=COURSE_ID,
                message="Explain Newton's third law of motion and action-reaction pairs."
            )
            t0 = time.time()
            resp = tutor_service.answer_question(request=req, db=db, request_type="tutor")
            tutor_result["latency"] = time.time() - t0
            tutor_result["grounded"] = resp.grounded
            tutor_result["answer"] = resp.answer[:100]
        except Exception as e:
            tutor_result["error"] = str(e)
        finally:
            db.close()

    t_eval = threading.Thread(target=run_eval)
    t_tutor = threading.Thread(target=run_tutor)

    t0_total = time.time()
    t_eval.start()
    t_tutor.start()

    t_tutor.join()
    t_eval.join()
    total_time = time.time() - t0_total

    print(f"Total Combined Duration: {total_time:.2f}s")
    print(f"Tutor Result: {tutor_result}")
    print(f"Evaluation Result: {eval_result}")
    return tutor_result, eval_result


if __name__ == "__main__":
    t_lat, _ = test_a_live_tutor()
    a_lat, _ = test_b_live_assessment()
    e_lat, _ = test_c_live_evaluation_single_case()
    tut_res, ev_res = test_d_concurrent_evaluation_and_tutor()

    print("\n" + "=" * 60)
    print("LIVE VERIFICATION SUMMARY:")
    print(f"Live Tutor Latency: {t_lat:.2f}s" if t_lat else "Live Tutor: Error/429")
    print(f"Live Assessment Latency: {a_lat:.2f}s" if a_lat else "Live Assessment: Error/429")
    print(f"Live 1-case Eval Latency: {e_lat:.2f}s" if e_lat else "Live 1-case Eval: Error/429")
    print(f"Concurrent Tutor Latency: {tut_res.get('latency', 'N/A')}s, Grounded: {tut_res.get('grounded')}")
    print(f"Concurrent Eval Latency: {ev_res.get('latency', 'N/A')}s, Status: {ev_res.get('status')}")
    print("=" * 60)
