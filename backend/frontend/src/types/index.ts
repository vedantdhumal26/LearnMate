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
  source_type?: string;
  title?: string;
  video_id?: string;
  canonical_url?: string;
  slide_count?: number;
  visual_count?: number;
  duration?: number;
  duration_seconds?: number;
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

export interface YouTubeSourcePayload {
  url: string;
}

export interface YouTubeSourceResponse {
  source_id: string;
  video_id: string;
  canonical_url: string;
  status: string;
  message: string;
  title?: string;
  duration_seconds?: number;
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

export interface ApiError extends Error {
  status?: number;
  detail?: string;
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
  student_id: string;
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
  student_id: string;
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
