import json
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.evaluation import EvaluationRun, EvaluationResult
from app.models.course import Course
from app.schemas.evaluation import (
    EvaluationRunRequest,
    EvaluationTestCase,
    EvaluationMetricsSummary,
    LearnerSimulationResult,
    EvaluationResultsResponse,
    EvaluationResultItem,
)
from app.schemas.tutor import TutorChatRequest
from app.services.rag.tutor_service import TutorService
from app.services.evaluation.citation_evaluator import CitationEvaluator
from app.services.evaluation.rag_evaluator import RAGEvaluator
from app.services.evaluation.assessment_evaluator import AssessmentEvaluator
from app.services.evaluation.learner_evaluator import LearnerModelEvaluator
from app.services.evaluation.fixtures import load_dataset_from_file_or_default
from app.core.config import settings
from app.core.logging_config import logger
from app.services.llm.llm_service import LLMRateLimitError
from app.services.llm.concurrency_gate import get_llm_gate

class EvaluationEngine:
    def __init__(
        self,
        tutor_service: Optional[TutorService] = None,
        rag_evaluator: Optional[RAGEvaluator] = None,
        citation_evaluator: Optional[CitationEvaluator] = None,
        assessment_evaluator: Optional[AssessmentEvaluator] = None,
        learner_evaluator: Optional[LearnerModelEvaluator] = None,
    ):
        self.tutor_service = tutor_service or TutorService()
        self.rag_evaluator = rag_evaluator or RAGEvaluator()
        self.citation_evaluator = citation_evaluator or CitationEvaluator()
        self.assessment_evaluator = assessment_evaluator or AssessmentEvaluator()
        self.learner_evaluator = learner_evaluator or LearnerModelEvaluator()

    def run_evaluation(
        self,
        db: Session,
        request: EvaluationRunRequest,
        existing_run_id: Optional[str] = None
    ) -> EvaluationRun:
        """
        Executes a complete evaluation run:
        1. Loads test cases from inline payload, disk path, or default fixture.
        2. Executes each test case against the live Tutor service.
        3. Validates citations and grounding correctness.
        4. Calculates RAG metrics (faithfulness, relevancy, precision, recall).
        5. Tracks cross-course isolation leakage.
        6. Runs assessment quality & duplicate-rate evaluations.
        7. Runs student profile mastery simulations.
        8. Persists results and updates status.
        """
        # Resolve target course
        target_course_id = request.course_id
        if not target_course_id:
            # Find candidate course with the most sources (preferring multimodal courses)
            all_courses = db.query(Course).all()
            if all_courses:
                sorted_courses = sorted(all_courses, key=lambda c: len(c.sources), reverse=True)
                target_course_id = sorted_courses[0].id
            else:
                target_course_id = "default-course"

        # Resolve evaluation mode ('quick' by default, or 'full')
        eval_mode = getattr(request, "mode", "quick") or "quick"
        if eval_mode not in ("quick", "full"):
            eval_mode = "quick"

        # Load dataset
        is_custom_dataset = bool(request.dataset and len(request.dataset) > 0)
        if is_custom_dataset:
            test_cases = list(request.dataset)
        else:
            test_cases = load_dataset_from_file_or_default(
                file_path=request.dataset_path,
                course_id=target_course_id,
                db=db
            )

        # Apply demo-safe bounds for quick mode
        max_cases_live = getattr(settings, "EVALUATION_MAX_CASES_LIVE", 3)
        if eval_mode == "quick":
            if is_custom_dataset:
                test_cases = test_cases[:max_cases_live]
            elif len(test_cases) > max_cases_live:
                # Default benchmark loaded: pick representative mix (1 supported, 1 unsupported, 1 isolation)
                sup_cases = [tc for tc in test_cases if tc.expected_grounded and not tc.is_course_isolation]
                unsup_cases = [tc for tc in test_cases if not tc.expected_grounded and not tc.is_course_isolation]
                iso_cases = [tc for tc in test_cases if tc.is_course_isolation]

                chosen = []
                if sup_cases:
                    chosen.append(sup_cases[0])
                if unsup_cases:
                    chosen.append(unsup_cases[0])
                if iso_cases:
                    chosen.append(iso_cases[0])

                if len(chosen) < max_cases_live:
                    for sc in sup_cases[1:]:
                        if len(chosen) >= max_cases_live:
                            break
                        if sc not in chosen:
                            chosen.append(sc)

                test_cases = chosen[:max_cases_live] if chosen else test_cases[:max_cases_live]
            logger.info(
                f"Quick evaluation mode active: executing {len(test_cases)} bounded real test cases "
                f"(max_cases_live={max_cases_live})."
            )
        else:
            logger.info(f"Full evaluation mode active: executing all {len(test_cases)} test cases.")

        # 1. Create or load EvaluationRun record
        if existing_run_id:
            run = db.query(EvaluationRun).filter(EvaluationRun.id == existing_run_id).first()
            if not run:
                run = EvaluationRun(
                    id=existing_run_id,
                    name=request.name,
                    status="running",
                    dataset_size=len(test_cases),
                    started_at=datetime.now(timezone.utc)
                )
                db.add(run)
            else:
                run.status = "running"
                run.dataset_size = len(test_cases)
        else:
            run = EvaluationRun(
                id=str(uuid.uuid4()),
                name=request.name,
                status="running",
                dataset_size=len(test_cases),
                started_at=datetime.now(timezone.utc)
            )
            db.add(run)
        db.commit()
        db.refresh(run)

        from app.services.llm.concurrency_gate import RequestPriority, current_request_priority, current_request_type
        token_priority = current_request_priority.set(RequestPriority.EVALUATION)
        token_type = current_request_type.set("evaluation")

        try:
            # Metrics tracking accumulators
            faithfulness_scores: List[float] = []
            relevancy_scores: List[float] = []
            precision_scores: List[float] = []
            recall_scores: List[float] = []

            total_citations_checked = 0
            valid_citations_checked = 0
            citation_failure_count = 0

            supported_count = 0
            supported_passed = 0
            unsupported_count = 0
            unsupported_passed = 0

            isolation_tests_count = 0
            isolation_failures = 0

            passed_test_cases = 0

            # 2. Execute test cases sequentially
            for tc in test_cases:
                # Handle isolation case course routing
                query_course_id = tc.course_id

                chat_req = TutorChatRequest(
                    course_id=query_course_id,
                    message=tc.question
                )

                actual_grounded = False
                answer = ""
                retrieved_sources = []
                failure_reasons = []

                # Check gate rate limit status before executing test case
                if get_llm_gate().is_rate_limited():
                    logger.warning(f"Aborting evaluation before test case '{tc.id}': provider rate limit active.")
                    raise LLMRateLimitError("AI service is temporarily busy (HTTP 429 rate limit active). Evaluation yielding.")

                try:
                    response = self.tutor_service.answer_question(
                        request=chat_req,
                        db=db,
                        request_type="evaluation",
                        priority=RequestPriority.EVALUATION
                    )
                    actual_grounded = response.grounded
                    answer = response.answer
                    retrieved_sources = response.sources or []
                except LLMRateLimitError as rle:
                    logger.warning(f"Evaluation hit rate limit on test case {tc.id}: {rle}. Aborting run.")
                    raise
                except Exception as e:
                    err_str = str(e).lower()
                    if "429" in err_str or "rate limit" in err_str or "temporarily busy" in err_str:
                        logger.warning(f"Evaluation hit rate limit (detected in message) on {tc.id}: {e}. Aborting.")
                        raise LLMRateLimitError("AI service is temporarily busy. Please try again.")
                    logger.warning(f"Error invoking tutor for test case {tc.id}: {e}")
                    failure_reasons.append(f"Tutor execution error: {str(e)}")
                    answer = f"Error: {str(e)}"

                # A. Evaluate Grounding
                if tc.is_course_isolation:
                    isolation_tests_count += 1
                    if actual_grounded or len(retrieved_sources) > 0:
                        isolation_failures += 1
                        failure_reasons.append("Course isolation violation: material leaked across course boundaries.")
                elif tc.expected_grounded:
                    supported_count += 1
                    if actual_grounded:
                        supported_passed += 1
                    else:
                        failure_reasons.append("False rejection: Expected grounded=True for supported question.")
                else:
                    unsupported_count += 1
                    if not actual_grounded and len(retrieved_sources) == 0:
                        unsupported_passed += 1
                    else:
                        failure_reasons.append("Overclaim: Expected grounded=False with empty sources for unsupported question.")

                # B. Evaluate Citations
                citation_correct = True
                if tc.expected_grounded and tc.expected_sources:
                    total_citations_checked += max(1, len(retrieved_sources))
                    c_valid, c_reason = self.citation_evaluator.evaluate_all(
                        citations=retrieved_sources,
                        expected_sources=tc.expected_sources,
                        course_id=query_course_id,
                        db=db
                    )
                    if c_valid:
                        valid_citations_checked += max(1, len(retrieved_sources))
                    else:
                        citation_correct = False
                        citation_failure_count += 1
                        failure_reasons.append(f"Citation validation failure: {c_reason}")
                elif not tc.expected_grounded:
                    if len(retrieved_sources) > 0:
                        citation_correct = False
                        citation_failure_count += len(retrieved_sources)
                        failure_reasons.append("Citations present on unsupported question.")

                # C. Compute RAG Metrics
                f_score = None
                r_score = None
                p_score = None
                rec_score = None

                if actual_grounded and retrieved_sources:
                    contexts = [s.excerpt for s in retrieved_sources if s.excerpt]
                    f_score = self.rag_evaluator.evaluate_faithfulness(
                        answer=answer,
                        retrieved_contexts=contexts,
                        use_llm=(eval_mode == "full")
                    )
                    if f_score is not None:
                        faithfulness_scores.append(f_score)

                    r_score = self.rag_evaluator.evaluate_answer_relevance(question=tc.question, answer=answer)
                    if r_score is not None:
                        relevancy_scores.append(r_score)

                    p_score = self.rag_evaluator.evaluate_context_precision(retrieved_sources=retrieved_sources, expected_sources=tc.expected_sources)
                    if p_score is not None:
                        precision_scores.append(p_score)

                    rec_score = self.rag_evaluator.evaluate_context_recall(retrieved_sources=retrieved_sources, expected_sources=tc.expected_sources)
                    if rec_score is not None:
                        recall_scores.append(rec_score)

                # D. Overall Case Pass/Fail
                case_passed = len(failure_reasons) == 0
                if case_passed:
                    passed_test_cases += 1

                # E. Store EvaluationResult record
                res_obj = EvaluationResult(
                    evaluation_run_id=run.id,
                    test_case_id=tc.id,
                    question=tc.question,
                    expected_grounded=tc.expected_grounded,
                    actual_grounded=actual_grounded,
                    answer=answer,
                    retrieved_sources=json.dumps([s.model_dump() for s in retrieved_sources]),
                    citation_correct=citation_correct,
                    faithfulness_score=f_score,
                    relevance_score=r_score,
                    context_precision=p_score,
                    context_recall=rec_score,
                    passed=case_passed,
                    failure_reason="; ".join(failure_reasons) if failure_reasons else None
                )
                db.add(res_obj)

            # 3. Assessment Evaluation
            assessment_valid_rate = None
            duplicate_rate = None
            assessment_qs_evaluated = None
            assessment_qs_valid = None
            dup_qs_evaluated = None
            dup_qs_detected = None

            if request.run_assessment_eval:
                try:
                    from app.models.assessment import Question
                    existing_qs = db.query(Question).filter(Question.course_id == target_course_id).all()
                    if not existing_qs and test_cases:
                        tc_cid = test_cases[0].course_id
                        if tc_cid and tc_cid != target_course_id:
                            tc_qs = db.query(Question).filter(Question.course_id == tc_cid).all()
                            if tc_qs:
                                existing_qs = tc_qs
                                target_course_id = tc_cid

                    if existing_qs:
                        q_eval = self.assessment_evaluator.evaluate_questions_quality(existing_qs, db)
                        assessment_valid_rate = q_eval.get("validity_rate")
                        assessment_qs_evaluated = q_eval.get("total_evaluated")
                        assessment_qs_valid = q_eval.get("valid_count")
                    else:
                        assessment_valid_rate = None
                        assessment_qs_evaluated = None
                        assessment_qs_valid = None

                    if eval_mode == "full":
                        course_obj = db.query(Course).filter(Course.id == target_course_id).first()
                        topic = course_obj.title if course_obj else "General"
                        dup_eval = self.assessment_evaluator.evaluate_duplicate_rate(
                            db=db,
                            course_id=target_course_id,
                            topic=topic,
                            rounds=2,
                            count_per_round=2
                        )
                        duplicate_rate = dup_eval.get("duplicate_rate")
                        dup_qs_evaluated = dup_eval.get("total_questions")
                        dup_qs_detected = dup_eval.get("duplicate_questions")

                        if duplicate_rate is None and existing_qs and len(existing_qs) >= 2:
                            dup_eval = self.assessment_evaluator.evaluate_duplicate_rate_from_questions(existing_qs)
                            duplicate_rate = dup_eval.get("duplicate_rate")
                            dup_qs_evaluated = dup_eval.get("total_questions")
                            dup_qs_detected = dup_eval.get("duplicate_questions")
                    else:
                        # In quick mode: evaluate duplicate rate from existing questions if available
                        if existing_qs and len(existing_qs) >= 2:
                            dup_eval = self.assessment_evaluator.evaluate_duplicate_rate_from_questions(existing_qs)
                            duplicate_rate = dup_eval.get("duplicate_rate")
                            dup_qs_evaluated = dup_eval.get("total_questions")
                            dup_qs_detected = dup_eval.get("duplicate_questions")
                        else:
                            duplicate_rate = None
                            dup_qs_evaluated = None
                            dup_qs_detected = None
                except Exception as a_err:
                    logger.warning(f"Note on assessment evaluation execution: {a_err}")

            # 4. Learner Model Simulation
            learner_sim_results: List[LearnerSimulationResult] = []
            if request.run_learner_simulations:
                try:
                    learner_sim_results = self.learner_evaluator.run_simulations(
                        db=db,
                        course_id=target_course_id,
                        topic="Neural Networks"
                    )
                except Exception as l_err:
                    logger.warning(f"Note on learner simulation execution: {l_err}")

            # 5. Compute Aggregate Summary
            grounding_total = supported_count + unsupported_count
            grounding_passed = supported_passed + unsupported_passed
            grounding_accuracy = round(grounding_passed / grounding_total, 3) if grounding_total > 0 else 1.0

            citation_accuracy = (
                round(valid_citations_checked / total_citations_checked, 3)
                if total_citations_checked > 0 else 1.0
            )

            summary = EvaluationMetricsSummary(
                faithfulness=round(sum(faithfulness_scores) / len(faithfulness_scores), 3) if faithfulness_scores else None,
                answer_relevancy=round(sum(relevancy_scores) / len(relevancy_scores), 3) if relevancy_scores else None,
                context_precision=round(sum(precision_scores) / len(precision_scores), 3) if precision_scores else None,
                context_recall=round(sum(recall_scores) / len(recall_scores), 3) if recall_scores else None,
                citation_accuracy=citation_accuracy,
                citation_failure_count=citation_failure_count,
                grounding_accuracy=grounding_accuracy,
                supported_questions_count=supported_count,
                supported_questions_passed=supported_passed,
                unsupported_questions_count=unsupported_count,
                unsupported_questions_passed=unsupported_passed,
                course_isolation_failures=isolation_failures,
                course_isolation_tests_count=isolation_tests_count,
                assessment_valid_question_rate=assessment_valid_rate,
                duplicate_rate=duplicate_rate,
                assessment_questions_evaluated=assessment_qs_evaluated,
                assessment_questions_valid=assessment_qs_valid,
                duplicate_questions_evaluated=dup_qs_evaluated,
                duplicate_questions_detected=dup_qs_detected,
                total_test_cases=len(test_cases),
                passed_test_cases=passed_test_cases
            )

            # 6. Finalize EvaluationRun record
            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc)
            run.summary_metrics = json.dumps(summary.model_dump())
            run.learner_simulation_results = json.dumps([s.model_dump() for s in learner_sim_results])
            db.commit()
            db.refresh(run)

            logger.info(
                f"EvaluationRun '{run.id}' completed: {passed_test_cases}/{len(test_cases)} passed, "
                f"citation_acc={citation_accuracy}, grounding_acc={grounding_accuracy}"
            )
            return run

        except LLMRateLimitError as rle:
            logger.warning(f"EvaluationRun '{run.id}' aborted due to rate limit: {rle}")
            db.rollback()
            run.status = "failed"
            run.error_message = "Evaluation failed: AI service rate limit reached (HTTP 429). Please try again later."
            run.completed_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(run)
            return run
        except Exception as e:
            logger.error(f"EvaluationRun '{run.id}' failed with error: {e}", exc_info=True)
            db.rollback()
            run.status = "failed"
            run.error_message = str(e)
            run.completed_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(run)
            return run
        finally:
            current_request_priority.reset(token_priority)
            current_request_type.reset(token_type)

    @staticmethod
    def get_results_response(run: EvaluationRun) -> EvaluationResultsResponse:
        """Construct full EvaluationResultsResponse schema from EvaluationRun record."""
        summary_dict = json.loads(run.summary_metrics) if run.summary_metrics else {}
        summary = EvaluationMetricsSummary.model_validate(summary_dict)

        learner_sims = []
        if run.learner_simulation_results:
            sim_list = json.loads(run.learner_simulation_results)
            learner_sims = [LearnerSimulationResult.model_validate(s) for s in sim_list]

        result_items = []
        failures = []
        for r in run.results:
            sources_list = json.loads(r.retrieved_sources) if r.retrieved_sources else []
            item = EvaluationResultItem(
                test_case_id=r.test_case_id,
                question=r.question,
                expected_grounded=r.expected_grounded,
                actual_grounded=r.actual_grounded,
                answer=r.answer,
                retrieved_sources=sources_list,
                citation_correct=r.citation_correct,
                faithfulness_score=r.faithfulness_score,
                relevance_score=r.relevance_score,
                context_precision=r.context_precision,
                context_recall=r.context_recall,
                passed=r.passed,
                failure_reason=r.failure_reason
            )
            result_items.append(item)
            if not r.passed:
                failures.append({
                    "test_case_id": r.test_case_id,
                    "question": r.question,
                    "failure_reason": r.failure_reason
                })

        return EvaluationResultsResponse(
            evaluation_id=run.id,
            status=run.status,
            dataset_size=run.dataset_size,
            started_at=run.started_at,
            completed_at=run.completed_at,
            summary=summary,
            learner_simulations=learner_sims,
            results=result_items,
            failures=failures
        )

_eval_engine_instance: Optional[EvaluationEngine] = None

def get_evaluation_engine() -> EvaluationEngine:
    global _eval_engine_instance
    if _eval_engine_instance is None:
        _eval_engine_instance = EvaluationEngine()
    return _eval_engine_instance
