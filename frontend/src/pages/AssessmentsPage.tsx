import { useCallback, useEffect, useState } from 'react';
import { useParams, Link, useNavigate, useSearchParams } from 'react-router-dom';
import {
  ArrowLeft,
  BarChart3,
  Plus,
  Loader2,
  AlertCircle,
  Sparkles,
  X,
} from 'lucide-react';
import { AppLayout } from '@/layouts/AppLayout';
import { EmptyState } from '@/components/EmptyState';
import { ErrorState } from '@/components/ErrorState';
import { api, getErrorMessage } from '@/lib/api';
import { useAuth } from '@/contexts/AuthContext';
import type {
  AssessmentDifficulty,
  AssessmentQuestionType,
  Course,
} from '@/types';

const DIFFICULTIES: { value: AssessmentDifficulty; label: string }[] = [
  { value: 'easy', label: 'Easy' },
  { value: 'medium', label: 'Medium' },
  { value: 'hard', label: 'Hard' },
];

const QUESTION_TYPES: { value: AssessmentQuestionType; label: string }[] = [
  { value: 'mcq', label: 'Multiple Choice' },
  { value: 'short_answer', label: 'Short Answer' },
  { value: 'numerical', label: 'Numerical' },
];

export function AssessmentsPage() {
  const { courseId } = useParams<{ courseId: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [searchParams] = useSearchParams();
  const [course, setCourse] = useState<Course | null>(null);
  const [courseLoading, setCourseLoading] = useState(true);
  const [courseError, setCourseError] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState('');

  const [topic, setTopic] = useState('');
  const [difficulty, setDifficulty] = useState<AssessmentDifficulty>('medium');
  const [questionType, setQuestionType] = useState<AssessmentQuestionType>('mcq');
  const [count, setCount] = useState(5);

  // Prefill from URL params (e.g. from learning dashboard recommendations)
  useEffect(() => {
    const prefilledTopic = searchParams.get('topic');
    const prefilledDifficulty = searchParams.get('difficulty');
    const prefilledCount = searchParams.get('count');
    if (prefilledTopic) {
      setTopic(prefilledTopic);
      setModalOpen(true);
    }
    if (prefilledDifficulty && ['easy', 'medium', 'hard'].includes(prefilledDifficulty)) {
      setDifficulty(prefilledDifficulty as AssessmentDifficulty);
    }
    if (prefilledCount) {
      const n = Number(prefilledCount);
      if (n >= 1 && n <= 20) {
        setCount(n);
      }
    }
  }, [searchParams]);

  const loadCourse = useCallback(async () => {
    if (!courseId) return;
    setCourseLoading(true);
    setCourseError('');
    try {
      const data = await api.getCourse(courseId);
      setCourse(data);
    } catch (err) {
      setCourseError(getErrorMessage(err));
    } finally {
      setCourseLoading(false);
    }
  }, [courseId]);

  useEffect(() => {
    loadCourse();
  }, [loadCourse]);

  const canGenerate = topic.trim().length > 0 && !generating;

  async function handleGenerate(e: React.FormEvent) {
    e.preventDefault();
    if (!courseId || !canGenerate) return;
    setGenerating(true);
    setGenError('');
    try {
      const assessment = await api.generateAssessment({
        course_id: courseId,
        student_id: user?.id,
        topic: topic.trim(),
        difficulty,
        question_type: questionType,
        count,
      });
      navigate(`/courses/${courseId}/assessments/${assessment.assessment_id}`);
    } catch (err) {
      const msg = getErrorMessage(err);
      if (msg.toLowerCase().includes('not enough') || msg.toLowerCase().includes('insufficient')) {
        setGenError("There's not enough course material to generate an assessment for this topic. Try uploading more material or choosing a different topic.");
      } else {
        setGenError(msg);
      }
    } finally {
      setGenerating(false);
    }
  }

  if (courseLoading) {
    return (
      <AppLayout>
        <div className="flex items-center gap-2 text-ink-500">
          <Loader2 className="h-5 w-5 animate-spin" />
          Loading…
        </div>
      </AppLayout>
    );
  }

  if (courseError && !course) {
    return (
      <AppLayout>
        <ErrorState message={courseError} onRetry={loadCourse} />
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <Link
        to={courseId ? `/courses/${courseId}` : '/dashboard'}
        className="inline-flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-700 dark:text-ink-400 dark:hover:text-ink-200 transition-colors mb-6"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Course
      </Link>

      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight text-ink-900 dark:text-white">
            Assessments
          </h1>
          <p className="mt-1.5 text-sm text-ink-500 dark:text-ink-400 max-w-lg">
            Generate AI-powered assessments from your course material. Each question is grounded in your uploaded sources with page-level citations.
          </p>
        </div>
        <button
          onClick={() => setModalOpen(true)}
          className="btn-primary shrink-0"
        >
          <Plus className="h-4 w-4" />
          Generate Assessment
        </button>
      </div>

      {/* Assessment history / empty state */}
      <div className="mt-8">
        <h2 className="font-display text-lg font-semibold text-ink-900 dark:text-white mb-4">
          Assessment History
        </h2>
        <EmptyState
          icon={<BarChart3 className="h-7 w-7" />}
          title="No assessments yet"
          description="Generate your first assessment to test your understanding of the course material."
          action={
            <button onClick={() => setModalOpen(true)} className="btn-primary">
              <Plus className="h-4 w-4" />
              Generate Assessment
            </button>
          }
        />
      </div>

      {/* Generate modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 animate-fade-in" onClick={() => !generating && setModalOpen(false)}>
          <div className="absolute inset-0 bg-ink-900/40 dark:bg-black/60 backdrop-blur-sm" />
          <div
            className="relative w-full max-w-lg rounded-2xl border border-ink-200 dark:border-ink-800 bg-white dark:bg-ink-900 shadow-pop animate-fade-in-up"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal header */}
            <div className="flex items-center justify-between border-b border-ink-100 dark:border-ink-800 px-5 py-4">
              <div className="flex items-center gap-2.5">
                <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600 text-white">
                  <Sparkles className="h-4.5 w-4.5" />
                </span>
                <h3 className="font-display text-base font-semibold text-ink-900 dark:text-white">
                  Generate Assessment
                </h3>
              </div>
              {!generating && (
                <button
                  onClick={() => setModalOpen(false)}
                  className="rounded-lg p-1.5 text-ink-400 hover:bg-ink-100 hover:text-ink-600 dark:text-ink-500 dark:hover:bg-ink-800 dark:hover:text-ink-300 transition-colors"
                  aria-label="Close"
                >
                  <X className="h-4.5 w-4.5" />
                </button>
              )}
            </div>

            {/* Modal body */}
            <form onSubmit={handleGenerate} className="px-5 py-5 space-y-4">
              <div>
                <label htmlFor="topic" className="label">
                  Topic <span className="text-err-500">*</span>
                </label>
                <input
                  id="topic"
                  type="text"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  placeholder="e.g. Nanoparticles"
                  className="input"
                  disabled={generating}
                  autoFocus
                  maxLength={200}
                />
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label htmlFor="difficulty" className="label">Difficulty</label>
                  <select
                    id="difficulty"
                    value={difficulty}
                    onChange={(e) => setDifficulty(e.target.value as AssessmentDifficulty)}
                    className="input"
                    disabled={generating}
                  >
                    {DIFFICULTIES.map((d) => (
                      <option key={d.value} value={d.value}>{d.label}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label htmlFor="questionType" className="label">Question Type</label>
                  <select
                    id="questionType"
                    value={questionType}
                    onChange={(e) => setQuestionType(e.target.value as AssessmentQuestionType)}
                    className="input"
                    disabled={generating}
                  >
                    {QUESTION_TYPES.map((q) => (
                      <option key={q.value} value={q.value}>{q.label}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label htmlFor="count" className="label">
                  Number of Questions: <span className="text-brand-600 dark:text-brand-400 font-semibold">{count}</span>
                </label>
                <input
                  id="count"
                  type="range"
                  min={1}
                  max={20}
                  value={count}
                  onChange={(e) => setCount(Number(e.target.value))}
                  className="w-full accent-brand-600"
                  disabled={generating}
                />
                <div className="flex justify-between text-xs text-ink-400 dark:text-ink-500 mt-1">
                  <span>1</span>
                  <span>20</span>
                </div>
              </div>

              {genError && (
                <div className="flex items-start gap-2.5 rounded-lg border border-err-200 dark:border-err-800 bg-err-50 dark:bg-err-950/40 px-4 py-3 animate-fade-in">
                  <AlertCircle className="h-5 w-5 text-err-500 shrink-0 mt-0.5" />
                  <p className="text-sm text-err-700 dark:text-err-300">{genError}</p>
                </div>
              )}

              <div className="flex items-center gap-3 pt-2">
                <button
                  type="submit"
                  disabled={!canGenerate}
                  className="btn-primary flex-1"
                >
                  {generating ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Generating…
                    </>
                  ) : (
                    <>
                      <Sparkles className="h-4 w-4" />
                      Generate
                    </>
                  )}
                </button>
                {!generating && (
                  <button
                    type="button"
                    onClick={() => setModalOpen(false)}
                    className="btn-secondary"
                  >
                    Cancel
                  </button>
                )}
              </div>
            </form>
          </div>
        </div>
      )}
    </AppLayout>
  );
}
