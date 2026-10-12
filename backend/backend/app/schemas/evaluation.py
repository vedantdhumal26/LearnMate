from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field

class ExpectedSource(BaseModel):
    source_id: Optional[str] = Field(default=None, description="Expected source document ID")
    file_name: Optional[str] = Field(default=None, description="Expected source file name")
    page: Optional[int] = Field(default=None, description="Expected PDF page number (1-indexed)")
    slide: Optional[int] = Field(default=None, description="Expected PPTX slide number (1-indexed)")
    start_seconds: Optional[float] = Field(default=None, description="Expected start seconds for audio/video/YouTube")
    end_seconds: Optional[float] = Field(default=None, description="Expected end seconds for audio/video/YouTube")
    modality: Optional[str] = Field(default=None, description="Expected modality (pdf, pptx, video, youtube)")

    model_config = ConfigDict(from_attributes=True)


class EvaluationTestCase(BaseModel):
    id: str = Field(..., description="Unique test case identifier (e.g. eval-001)")
    course_id: str = Field(..., description="Target course ID for the evaluation query")
    question: str = Field(..., min_length=1, description="Evaluation question to ask the tutor")
    expected_answer: Optional[str] = Field(default=None, description="Reference expected answer text")
    expected_sources: List[ExpectedSource] = Field(default_factory=list, description="Expected citation sources")
    expected_grounded: bool = Field(default=True, description="Whether the question is expected to be grounded")
    is_course_isolation: bool = Field(default=False, description="Whether this case tests cross-course isolation leakage")
    source_course_id: Optional[str] = Field(default=None, description="Source course ID containing the content for isolation tests")

    model_config = ConfigDict(from_attributes=True)


class EvaluationRunRequest(BaseModel):
    name: str = Field(default="LearnSphere System Evaluation", description="Descriptive name for the evaluation run")
    mode: str = Field(default="quick", description="Evaluation mode: 'quick' (lightweight demo, max cases bounded by EVALUATION_MAX_CASES_LIVE) or 'full' (complete 40-case benchmark)")
    dataset_path: Optional[str] = Field(default=None, description="Optional path to a JSON dataset file on disk")
    dataset: Optional[List[EvaluationTestCase]] = Field(default=None, description="Optional inline list of test cases")
    course_id: Optional[str] = Field(default=None, description="Optional course ID to bind dataset cases to if unspecified")
    run_learner_simulations: bool = Field(default=True, description="Whether to execute simulated learner profile evaluations")
    run_assessment_eval: bool = Field(default=True, description="Whether to execute assessment question generation & duplicate evaluation")
    sync: bool = Field(default=True, description="Whether to run synchronously and complete before returning")

    model_config = ConfigDict(from_attributes=True)


class EvaluationRunResponse(BaseModel):
    evaluation_id: str = Field(..., description="Unique evaluation run ID")
    status: str = Field(..., description="Status: started, running, completed, failed")

    model_config = ConfigDict(from_attributes=True)


class EvaluationStatusResponse(BaseModel):
    evaluation_id: str
    status: str
    dataset_size: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    failure_reason: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class EvaluationMetricsSummary(BaseModel):
    faithfulness: Optional[float] = Field(default=None, description="Faithfulness of answer to retrieved context (0.0 to 1.0)")
    answer_relevancy: Optional[float] = Field(default=None, description="Relevancy of answer to the user question (0.0 to 1.0)")
    context_precision: Optional[float] = Field(default=None, description="Precision of retrieved chunks against expected sources")
    context_recall: Optional[float] = Field(default=None, description="Recall of expected sources in retrieved chunks")
    citation_accuracy: float = Field(..., description="Percentage of citations verified accurate (0.0 to 1.0)")
    citation_failure_count: int = Field(default=0, description="Total number of invalid citations detected")
    grounding_accuracy: float = Field(..., description="Percentage of correct grounded vs rejected decisions")
    supported_questions_count: int = Field(default=0, description="Count of supported questions evaluated")
    supported_questions_passed: int = Field(default=0, description="Count of supported questions returning grounded=True")
    unsupported_questions_count: int = Field(default=0, description="Count of off-material questions evaluated")
    unsupported_questions_passed: int = Field(default=0, description="Count of off-material questions properly rejected")
    course_isolation_failures: int = Field(default=0, description="Count of queries that leaked material across course boundaries")
    course_isolation_tests_count: int = Field(default=0, description="Total course isolation test cases evaluated")
    assessment_valid_question_rate: Optional[float] = Field(default=None, description="Percentage of generated assessment questions that passed verification")
    duplicate_rate: Optional[float] = Field(default=None, description="Question duplicate rate across repeated assessment generations")
    assessment_questions_evaluated: Optional[int] = Field(default=None, description="Total assessment questions evaluated for validity")
    assessment_questions_valid: Optional[int] = Field(default=None, description="Total assessment questions that passed verification")
    duplicate_questions_evaluated: Optional[int] = Field(default=None, description="Total questions evaluated for duplicate detection")
    duplicate_questions_detected: Optional[int] = Field(default=None, description="Total duplicate questions detected")
    total_test_cases: int = Field(default=0, description="Total test cases executed")
    passed_test_cases: int = Field(default=0, description="Total test cases passed")

    model_config = ConfigDict(from_attributes=True)


class LearnerSimulationResult(BaseModel):
    student_profile: str = Field(..., description="Profile type: high_performer, mixed_performer, struggling")
    student_id: str
    course_id: str
    topic: str
    mastery_before: float
    mastery_after: float
    mastery_gain: float
    confidence_before: float
    confidence_after: float
    weak_topics_detected: List[str] = Field(default_factory=list)
    recommendations_count: int = 0
    recommendations_changed: bool = Field(default=False, description="Whether recommendations dynamically responded to student performance changes")

    model_config = ConfigDict(from_attributes=True)


class EvaluationResultItem(BaseModel):
    test_case_id: str
    question: str
    expected_grounded: bool
    actual_grounded: bool
    answer: str
    retrieved_sources: List[Dict[str, Any]] = Field(default_factory=list)
    citation_correct: bool
    faithfulness_score: Optional[float] = None
    relevance_score: Optional[float] = None
    context_precision: Optional[float] = None
    context_recall: Optional[float] = None
    passed: bool
    failure_reason: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class EvaluationResultsResponse(BaseModel):
    evaluation_id: str
    status: str
    dataset_size: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    summary: EvaluationMetricsSummary
    learner_simulations: List[LearnerSimulationResult] = Field(default_factory=list)
    results: List[EvaluationResultItem] = Field(default_factory=list)
    failures: List[Dict[str, Any]] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
