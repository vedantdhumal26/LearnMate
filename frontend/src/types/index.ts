export interface Course {
  id: string;
  title: string;
  description?: string;
  created_at: string;
  source_count?: number;
  chunk_count?: number;
  sources?: Source[];
}

export interface Source {
  id: string;
  file_name: string;
  file_type: string;
  processing_status: string;
  created_at: string;
  source_type?: string | null;
  modality?: SourceModality | null;
  title?: string | null;
  video_id?: string | null;
  canonical_url?: string | null;
  slide_count?: number;
  visual_count?: number;
  duration?: number;
  segment_count?: number;
}

export type SourceModality = 'pdf' | 'pptx' | 'video' | 'youtube';

export interface TutorSource {
  source_id: string;
  file_name: string;
  page?: number | null;
  slide?: number | null;
  start_seconds?: number | null;
  end_seconds?: number | null;
  excerpt: string;
  modality?: string | null;
  video_id?: string | null;
  canonical_url?: string | null;
}

export interface YouTubeSourceRequest {
  url: string;
}

export interface YouTubeSourceResponse {
  source_id: string;
  video_id: string;
  canonical_url: string;
  status: string;
  message: string;
  title?: string | null;
  duration_seconds?: number | null;
}

export interface UploadResponse {
  source_id: string;
  file_name: string;
  status: string;
  id?: string;
  processing_status?: string;
}

export interface TutorResponse {
  answer: string;
  grounded: boolean;
  sources: TutorSource[];
  response_type?: string;
}

export interface CreateCoursePayload {
  title: string;
  description?: string;
}

export interface UpdateCoursePayload {
  title?: string;
  description?: string;
}

export interface ApiError extends Error {
  status?: number;
  detail?: string;
  rawDetail?: unknown;
}

// ── Authentication types ──

export interface User {
  id: string;
  email: string;
  display_name: string;
  created_at?: string;
}

export interface AuthResponse {
  access_token: string;
  token_type?: string;
  user: User;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface SignupRequest {
  email: string;
  password: string;
  display_name: string;
}

export interface UpdateUserPayload {
  display_name?: string;
  email?: string;
}

// ── Assessment types (matching exact backend contract) ──

export type AssessmentDifficulty = 'easy' | 'medium' | 'hard';
export type AssessmentQuestionType = 'mcq' | 'short_answer' | 'numerical';

export interface AssessmentSource {
  source_id: string;
  file_name: string;
  page?: number | null;
  slide?: number | null;
  start_seconds?: number | null;
  end_seconds?: number | null;
  excerpt: string;
  modality?: string | null;
  video_id?: string | null;
  canonical_url?: string | null;
}

export interface AssessmentQuestion {
  id: string;
  question_type: AssessmentQuestionType;
  question: string;
  options: string[] | null;
  difficulty: AssessmentDifficulty;
  topic: string;
  sources: AssessmentSource[];
}

export interface Assessment {
  assessment_id: string;
  title: string;
  course_id: string;
  student_id: string | null;
  questions: AssessmentQuestion[];
}

export interface GenerateAssessmentPayload {
  course_id: string;
  student_id?: string;
  topic: string;
  difficulty: AssessmentDifficulty;
  question_type: AssessmentQuestionType;
  count: number;
}

export interface AssessmentAnswer {
  question_id: string;
  answer: string;
}

export interface SubmitAssessmentPayload {
  student_id?: string;
  answers: AssessmentAnswer[];
}

export interface QuestionResult {
  question_id: string;
  correct: boolean;
  feedback: string;
  sources: AssessmentSource[];
}

export interface TopicPerformance {
  topic: string;
  score: number;
  correct: number;
  total: number;
}

export interface AssessmentResult {
  assessment_id: string;
  score: number;
  correct: number;
  total: number;
  question_results: QuestionResult[];
  topic_performance: TopicPerformance[];
}

// ── Learner model types (matching exact backend contract) ──

export interface LearnerTopicMastery {
  topic: string;
  mastery_score: number;
  confidence: number;
  attempts: number;
  correct_attempts: number;
  last_interaction: string;
}

export interface LearnerMastery {
  student_id: string;
  course_id: string;
  topics: LearnerTopicMastery[];
}

export interface WeakTopic {
  topic: string;
  mastery_score: number;
  reason: string;
}

export interface StrongTopic {
  topic: string;
  mastery_score: number;
}

export interface RecentTopic {
  topic: string;
  mastery_score: number;
  last_interaction: string;
}

export interface LearnerSummary {
  overall_mastery: number;
  strong_topics: StrongTopic[];
  weak_topics: WeakTopic[];
  recent_topics: RecentTopic[];
  status: string;
}

export type RecommendationPriority = 'high' | 'medium' | 'low';
export type RecommendedAction = 'practice' | 'review' | 'diagnostic';

export interface Recommendation {
  topic: string;
  priority: RecommendationPriority;
  reason: string;
  recommended_action: RecommendedAction;
  recommended_difficulty: AssessmentDifficulty;
  recommended_question_count: number;
}

export interface LearnerRecommendations {
  recommendations: Recommendation[];
}

export type StudyPlanAction =
  | 'practice'
  | 'tutor_review'
  | 'review_material'
  | 'challenge'
  | 'diagnostic'
  | string;

export interface StudyPlanItem {
  day: number;
  topic: string;
  priority: RecommendationPriority;
  action: StudyPlanAction;
  difficulty: AssessmentDifficulty;
  question_count: number;
  reason: string;
}

export interface StudyPlanResponse {
  student_id: string;
  course_id: string;
  plan_duration_days: number;
  plan: StudyPlanItem[];
}

export type StudyPlan = StudyPlanResponse;

// ── Evaluation types (matching exact backend contract) ──

export type EvaluationStatusType = 'idle' | 'starting' | 'pending' | 'running' | 'started' | 'completed' | 'failed';

export interface ExpectedSource {
  source_id?: string | null;
  file_name?: string | null;
  page?: number | null;
  slide?: number | null;
  start_seconds?: number | null;
  end_seconds?: number | null;
  modality?: string | null;
}

export interface EvaluationTestCase {
  id: string;
  course_id: string;
  question: string;
  expected_answer?: string | null;
  expected_sources?: ExpectedSource[];
  expected_grounded?: boolean;
  is_course_isolation?: boolean;
  source_course_id?: string | null;
}

export interface EvaluationRunRequest {
  name?: string;
  dataset_path?: string | null;
  dataset?: EvaluationTestCase[] | null;
  course_id?: string | null;
  run_learner_simulations?: boolean;
  run_assessment_eval?: boolean;
  sync?: boolean;
}

export interface EvaluationRun {
  evaluation_id: string;
  status: EvaluationStatusType;
}

export interface EvaluationStatus {
  evaluation_id: string;
  status: EvaluationStatusType;
  dataset_size?: number;
  started_at?: string;
  completed_at?: string | null;
  failure_reason?: string | null;
  error?: string | null;
}

export interface RagMetrics {
  answer_relevancy?: number | null;
  faithfulness?: number | null;
  context_precision?: number | null;
  context_recall?: number | null;
}

export interface GroundingMetrics {
  grounding_accuracy?: number | null;
  supported_questions?: number | null;
  supported_total?: number | null;
  unsupported_questions_rejected?: number | null;
  unsupported_total?: number | null;
}

export interface CitationMetrics {
  citation_accuracy?: number | null;
  citation_failures?: number | null;
  modality_breakdown?: Record<string, { accuracy?: number | null; total?: number | null }> | null;
}

export interface CourseIsolation {
  failures?: number | null;
  total?: number | null;
}

export interface AssessmentQuality {
  validity?: number | null;
  assessment_valid_question_rate?: number | null;
  duplicate_rate?: number | null;
  question_quality?: number | null;
  assessment_questions_evaluated?: number | null;
  assessment_questions_valid?: number | null;
  duplicate_questions_evaluated?: number | null;
  duplicate_questions_detected?: number | null;
}

export interface LearnerSimulation {
  student_profile: string; // 'high_performer' | 'mixed_performer' | 'struggling'
  student_id: string;
  course_id: string;
  topic: string;
  mastery_before: number;
  mastery_after: number;
  mastery_gain: number;
  confidence_before: number;
  confidence_after: number;
  weak_topics_detected?: string[];
  recommendations_count?: number;
  recommendations_changed?: boolean;
  // Legacy / UI helper fields
  before?: number | null;
  after?: number | null;
  recommendations?: string[] | null;
}

export type LearnerSimulationResult = LearnerSimulation;

export interface LearnerSimulations {
  high_performer?: LearnerSimulationResult | null;
  mixed_performer?: LearnerSimulationResult | null;
  struggling_learner?: LearnerSimulationResult | null;
}

export interface EvaluationFailure {
  test_case_id?: string;
  question?: string;
  failure_reason?: string | null;
  reason?: string | null;
  citation_issue?: string | null;
}

export interface EvaluationResultItem {
  test_case_id: string;
  question: string;
  expected_grounded: boolean;
  actual_grounded: boolean;
  answer: string;
  retrieved_sources?: Array<Record<string, unknown>>;
  citation_correct: boolean;
  faithfulness_score?: number | null;
  relevance_score?: number | null;
  context_precision?: number | null;
  context_recall?: number | null;
  passed: boolean;
  failure_reason?: string | null;
}

export interface EvaluationSummary {
  faithfulness?: number | null;
  answer_relevancy?: number | null;
  context_precision?: number | null;
  context_recall?: number | null;
  citation_accuracy?: number | null;
  citation_failure_count?: number | null;
  citation_failures?: number | null;
  grounding_accuracy?: number | null;
  supported_questions_count?: number | null;
  supported_questions_passed?: number | null;
  supported_questions?: number | null;
  supported_total?: number | null;
  unsupported_questions_count?: number | null;
  unsupported_questions_passed?: number | null;
  unsupported_questions_rejected?: number | null;
  unsupported_total?: number | null;
  course_isolation_failures?: number | null;
  course_isolation_tests_count?: number | null;
  assessment_valid_question_rate?: number | null;
  assessment_questions_evaluated?: number | null;
  assessment_questions_valid?: number | null;
  duplicate_rate?: number | null;
  duplicate_questions_evaluated?: number | null;
  duplicate_questions_detected?: number | null;
  total_test_cases?: number | null;
  passed_test_cases?: number | null;
  dataset_size?: number | null;
}

export interface EvaluationResult {
  evaluation_id: string;
  status: EvaluationStatusType;
  dataset_size?: number | null;
  started_at?: string;
  completed_at?: string | null;
  summary: EvaluationSummary;
  learner_simulations?: LearnerSimulation[] | LearnerSimulations | null;
  results?: EvaluationResultItem[];
  failures?: EvaluationFailure[];
  error?: string | null;
  rag_metrics?: RagMetrics | null;
  grounding?: GroundingMetrics | null;
  citation_quality?: CitationMetrics | null;
  course_isolation?: CourseIsolation | null;
  assessment_quality?: AssessmentQuality | null;
}
