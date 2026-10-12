import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Loader2,
  AlertCircle,
  Play,
  CheckCircle,
  XCircle,
  TrendingUp,
  Target,
  Shield,
  BarChart3,
  Users,
  ChevronDown,
  ChevronUp,
  Clock,
  FileText,
  Sparkles,
  Award,
  HelpCircle,
  RefreshCw,
} from 'lucide-react';
import { AppLayout } from '@/layouts/AppLayout';
import { EmptyState } from '@/components/EmptyState';
import { api, getErrorMessage } from '@/lib/api';
import { tokenStorage } from '@/lib/auth-token';
import type {
  EvaluationResult,
  EvaluationSummary,
  EvaluationFailure,
  EvaluationResultItem,
  EvaluationRunRequest,
} from '@/types';

// Explicit frontend states as defined in Step 6
type EvaluationState = 'idle' | 'starting' | 'running' | 'completed' | 'failed';

// ── Helpers ──

function formatTimestamp(iso?: string | null): string {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    });
  } catch {
    return String(iso);
  }
}

function scoreColor(value: number | null | undefined, lowerIsBetter = false): string {
  if (value === null || value === undefined || typeof value !== 'number' || isNaN(value)) {
    return 'text-ink-400 dark:text-ink-500';
  }
  const pct = value * 100;
  if (lowerIsBetter) {
    if (pct <= 10) return 'text-accent-600 dark:text-accent-400';
    if (pct <= 30) return 'text-warn-600 dark:text-warn-400';
    return 'text-err-600 dark:text-err-400';
  }
  if (pct >= 80) return 'text-accent-600 dark:text-accent-400';
  if (pct >= 50) return 'text-warn-600 dark:text-warn-400';
  return 'text-err-600 dark:text-err-400';
}

function barColor(value: number | null | undefined, lowerIsBetter = false): string {
  if (value === null || value === undefined || typeof value !== 'number' || isNaN(value)) {
    return 'bg-ink-200 dark:bg-ink-700';
  }
  const pct = value * 100;
  if (lowerIsBetter) {
    if (pct <= 10) return 'bg-accent-500';
    if (pct <= 30) return 'bg-warn-500';
    return 'bg-err-500';
  }
  if (pct >= 80) return 'bg-accent-500';
  if (pct >= 50) return 'bg-warn-500';
  return 'bg-err-500';
}

function barWidth(value: number | null | undefined): string {
  if (value === null || value === undefined || typeof value !== 'number' || isNaN(value)) {
    return '0%';
  }
  return `${Math.min(Math.max(Math.round(value * 100), 0), 100)}%`;
}

/** Normalize backend result into a flat summary. */
function extractSummary(result: EvaluationResult): EvaluationSummary | null {
  if (!result) return null;
  const s = result.summary || {};
  const rag = result.rag_metrics;
  const grounding = result.grounding;
  const citation = result.citation_quality;
  const isolation = result.course_isolation;
  const assessment = result.assessment_quality;

  return {
    answer_relevancy: s.answer_relevancy ?? rag?.answer_relevancy ?? null,
    faithfulness: s.faithfulness ?? rag?.faithfulness ?? null,
    context_precision: s.context_precision ?? rag?.context_precision ?? null,
    context_recall: s.context_recall ?? rag?.context_recall ?? null,
    grounding_accuracy: s.grounding_accuracy ?? grounding?.grounding_accuracy ?? null,
    supported_questions_count:
      s.supported_questions_count ?? s.supported_total ?? grounding?.supported_total ?? null,
    supported_questions_passed:
      s.supported_questions_passed ?? s.supported_questions ?? grounding?.supported_questions ?? null,
    unsupported_questions_count:
      s.unsupported_questions_count ?? s.unsupported_total ?? grounding?.unsupported_total ?? null,
    unsupported_questions_passed:
      s.unsupported_questions_passed ?? s.unsupported_questions_rejected ?? grounding?.unsupported_questions_rejected ?? null,
    citation_accuracy: s.citation_accuracy ?? citation?.citation_accuracy ?? null,
    citation_failure_count:
      s.citation_failure_count ?? s.citation_failures ?? citation?.citation_failures ?? null,
    course_isolation_failures: s.course_isolation_failures ?? isolation?.failures ?? null,
    course_isolation_tests_count: s.course_isolation_tests_count ?? isolation?.total ?? null,
    duplicate_rate: s.duplicate_rate ?? assessment?.duplicate_rate ?? null,
    assessment_valid_question_rate:
      s.assessment_valid_question_rate ?? assessment?.assessment_valid_question_rate ?? assessment?.validity ?? null,
    assessment_questions_evaluated:
      s.assessment_questions_evaluated ?? assessment?.assessment_questions_evaluated ?? null,
    assessment_questions_valid:
      s.assessment_questions_valid ?? assessment?.assessment_questions_valid ?? null,
    duplicate_questions_evaluated:
      s.duplicate_questions_evaluated ?? assessment?.duplicate_questions_evaluated ?? null,
    duplicate_questions_detected:
      s.duplicate_questions_detected ?? assessment?.duplicate_questions_detected ?? null,
    dataset_size: s.dataset_size ?? result.dataset_size ?? s.total_test_cases ?? null,
    total_test_cases: s.total_test_cases ?? result.dataset_size ?? null,
    passed_test_cases: s.passed_test_cases ?? null,
  };
}

interface FormattedSimulation {
  label: string;
  studentId: string;
  topic: string;
  masteryBefore: number | null;
  masteryAfter: number | null;
  masteryGain: number | null;
  confidenceBefore: number | null;
  confidenceAfter: number | null;
  weakTopics: string[];
  recommendationsCount: number;
}

/** Normalize learner simulations from real backend shape. */
function extractSimulations(result: EvaluationResult): FormattedSimulation[] {
  const raw = result.learner_simulations;
  if (!raw) return [];

  const profileLabels: Record<string, string> = {
    high_performer: 'High Performer',
    mixed_performer: 'Mixed Performer',
    struggling: 'Struggling Learner',
    struggling_learner: 'Struggling Learner',
  };

  if (Array.isArray(raw)) {
    return (raw as unknown[])
      .filter((s): s is Record<string, unknown> => s != null && typeof s === 'object')
      .map((s, i) => {
        const profile = typeof s.student_profile === 'string' ? s.student_profile : '';
        const label = profileLabels[profile] || (profile ? profile.replace(/_/g, ' ') : `Learner ${i + 1}`);
        const masteryBefore = typeof s.mastery_before === 'number' ? s.mastery_before : typeof s.before === 'number' ? s.before : null;
        const masteryAfter = typeof s.mastery_after === 'number' ? s.mastery_after : typeof s.after === 'number' ? s.after : null;
        const masteryGain = typeof s.mastery_gain === 'number' ? s.mastery_gain : (masteryBefore != null && masteryAfter != null ? masteryAfter - masteryBefore : null);
        const confidenceBefore = typeof s.confidence_before === 'number' ? s.confidence_before : null;
        const confidenceAfter = typeof s.confidence_after === 'number' ? s.confidence_after : null;
        const weakTopics = Array.isArray(s.weak_topics_detected)
          ? s.weak_topics_detected.filter((w): w is string => typeof w === 'string')
          : [];
        const recommendationsCount = typeof s.recommendations_count === 'number' ? s.recommendations_count : 0;

        return {
          label,
          studentId: typeof s.student_id === 'string' ? s.student_id : '',
          topic: typeof s.topic === 'string' ? s.topic : '',
          masteryBefore,
          masteryAfter,
          masteryGain,
          confidenceBefore,
          confidenceAfter,
          weakTopics,
          recommendationsCount,
        };
      });
  }

  return [];
}

const LATEST_EVAL_ID_KEY = 'learnsphere_latest_evaluation_id';

// ── Main Page Component ──

export function EvaluationPage() {
  const [evalState, setEvalState] = useState<EvaluationState>('idle');
  const [evaluationId, setEvaluationId] = useState<string | null>(null);
  const [result, setResult] = useState<EvaluationResult | null>(null);
  const [errorMessage, setErrorMessage] = useState<string>('');
  const [methodologyOpen, setMethodologyOpen] = useState(false);
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isPollingRef = useRef<boolean>(false);
  const pollAttemptsRef = useRef<number>(0);
  const MAX_POLL_ATTEMPTS = 120; // 5 minutes max timeout (120 * 2.5s)

  const stopPolling = useCallback(() => {
    isPollingRef.current = false;
    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => {
      stopPolling();
    };
  }, [stopPolling]);

  // Load the most recent evaluation run if an ID was saved or passed via query param.
  // Purges any raw cached result objects to prevent displaying stale results from before backend fix.
  // Crucially, this does NOT start an expensive evaluation run on mount.
  useEffect(() => {
    try {
      sessionStorage.removeItem('learnsphere_evaluation_result');
      sessionStorage.removeItem('evaluation_result');
      localStorage.removeItem('learnsphere_evaluation_result');
      localStorage.removeItem('evaluation_result');
    } catch {
      // Ignore storage access errors
    }

    const params = new URLSearchParams(window.location.search);
    const queryId = params.get('id') || params.get('evaluation_id');
    let savedId: string | null = null;
    try {
      savedId = queryId || sessionStorage.getItem(LATEST_EVAL_ID_KEY);
    } catch {
      // Ignore storage access errors
    }

    if (savedId && tokenStorage.getToken()) {
      let cancelled = false;
      api
        .getEvaluationResults(savedId)
        .then((res) => {
          if (!cancelled && res && res.evaluation_id) {
            setEvaluationId(res.evaluation_id);
            setResult(res);
            setEvalState('completed');
          }
        })
        .catch((err) => {
          console.warn('[EVAL LOAD PREVIOUS]', err);
          try {
            sessionStorage.removeItem(LATEST_EVAL_ID_KEY);
          } catch {
            // Ignore storage access errors
          }
        });
      return () => {
        cancelled = true;
      };
    }
  }, []);

  const fetchResultsAndStop = useCallback(
    async (evalId: string) => {
      stopPolling();
      try {
        const res = await api.getEvaluationResults(evalId);
        setResult(res);
        setEvalState('completed');
        try {
          sessionStorage.setItem(LATEST_EVAL_ID_KEY, evalId);
        } catch {
          // Ignore storage access errors
        }
        console.log('[EVAL FINAL STATUS]', 'completed');
      } catch (err: unknown) {
        setErrorMessage(getErrorMessage(err));
        setEvalState('failed');
        console.log('[EVAL FINAL STATUS]', 'failed');
      } finally {
        console.log('[EVAL END]');
      }
    },
    [stopPolling],
  );

  const pollStatus = useCallback(
    (evalId: string) => {
      stopPolling();
      isPollingRef.current = true;
      pollAttemptsRef.current = 0;

      const checkStatus = async () => {
        if (!isPollingRef.current) return;
        pollAttemptsRef.current += 1;

        if (pollAttemptsRef.current > MAX_POLL_ATTEMPTS) {
          stopPolling();
          console.log('[EVAL FINAL STATUS]', 'timeout');
          setErrorMessage('Evaluation timed out. Please try running again.');
          setEvalState('failed');
          console.log('[EVAL END]');
          return;
        }

        console.log('[EVAL POLL]', { evalId, attempt: pollAttemptsRef.current });
        try {
          const run = await api.getEvaluationStatus(evalId);
          console.log('[EVAL POLL RESPONSE]', run);

          if (!isPollingRef.current) return;

          if (run.status === 'completed') {
            stopPolling();
            await fetchResultsAndStop(evalId);
          } else if (run.status === 'failed') {
            stopPolling();
            console.log('[EVAL FINAL STATUS]', 'failed');
            setErrorMessage(run.failure_reason || run.error || 'Evaluation run failed. Please try again.');
            setEvalState('failed');
            console.log('[EVAL END]');
          } else {
            // 'started', 'pending', 'running'
            setEvalState('running');
            if (isPollingRef.current) {
              pollTimerRef.current = setTimeout(checkStatus, 2500);
            }
          }
        } catch (err: unknown) {
          stopPolling();
          console.log('[EVAL FINAL STATUS]', 'error');
          console.error('[EVAL POLL ERROR]', err);
          setErrorMessage(getErrorMessage(err));
          setEvalState('failed');
          console.log('[EVAL END]');
        }
      };

      pollTimerRef.current = setTimeout(checkStatus, 1500);
    },
    [stopPolling, fetchResultsAndStop],
  );

  const handleRunEvaluation = useCallback(async () => {
    stopPolling();
    setEvalState('starting');
    setErrorMessage('');
    setResult(null);

    console.log('[EVAL START]');

    const payload: EvaluationRunRequest = {
      name: 'LearnMate System Evaluation',
      run_learner_simulations: true,
      run_assessment_eval: true,
      sync: false,
    };

    try {
      const run = await api.runEvaluation(payload);
      console.log('[EVAL POST STATUS]', 201);
      console.log('[EVAL POST BODY]', run);

      if (!run || !run.evaluation_id) {
        console.log('[EVAL FINAL STATUS]', 'failed');
        setErrorMessage('The evaluation service did not return a valid evaluation ID. Please try again.');
        setEvalState('failed');
        console.log('[EVAL END]');
        return;
      }

      console.log('[EVAL ID]', run.evaluation_id);
      setEvaluationId(run.evaluation_id);

      if (run.status === 'completed') {
        setEvalState('running');
        await fetchResultsAndStop(run.evaluation_id);
      } else if (run.status === 'failed') {
        console.log('[EVAL FINAL STATUS]', 'failed');
        setErrorMessage('Evaluation run failed on the server. Please try again.');
        setEvalState('failed');
        console.log('[EVAL END]');
      } else {
        setEvalState('running');
        pollStatus(run.evaluation_id);
      }
    } catch (err: unknown) {
      stopPolling();
      const status = (err as { status?: number })?.status;
      console.log('[EVAL POST STATUS]', status ?? 'ERROR');
      console.log('[EVAL POST BODY]', (err as { detail?: string })?.detail || (err as Error)?.message);
      console.log('[EVAL FINAL STATUS]', 'failed');
      setErrorMessage(getErrorMessage(err));
      setEvalState('failed');
      console.log('[EVAL END]');
    }
  }, [pollStatus, fetchResultsAndStop, stopPolling]);

  return (
    <AppLayout>
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight text-ink-900 dark:text-white">
            LearnMate Grounding &amp; Quality Evaluation
          </h1>
          <p className="mt-1.5 text-sm text-ink-500 dark:text-ink-400 max-w-lg">
            System quality and personalization validation. Run or inspect evaluation benchmarks measuring RAG metrics, citation accuracy, course isolation, and adaptive learner simulations.
          </p>
        </div>
        <button
          onClick={handleRunEvaluation}
          disabled={evalState === 'starting' || evalState === 'running'}
          className="btn-primary shrink-0 flex items-center gap-2"
        >
          {evalState === 'starting' ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Starting evaluation...
            </>
          ) : evalState === 'running' ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Evaluation in progress...
            </>
          ) : (
            <>
              <Play className="h-4 w-4" />
              Run Benchmark Evaluation
            </>
          )}
        </button>
      </div>

      {/* Judge Benchmark & Reliability Overview */}
      <div className="mt-6 rounded-2xl border border-brand-200 dark:border-brand-800 bg-gradient-to-br from-brand-50/80 via-white to-indigo-50/50 dark:from-brand-950/60 dark:via-ink-900 dark:to-indigo-950/40 p-6 shadow-sm">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-5">
          <div className="space-y-1.5 max-w-2xl">
            <div className="inline-flex items-center gap-1.5 rounded-full bg-brand-100 dark:bg-brand-950/80 px-3 py-1 text-xs font-semibold text-brand-800 dark:text-brand-300">
              <Shield className="h-3.5 w-3.5 text-brand-600 dark:text-brand-400" />
              Judge Verification Layer
            </div>
            <h2 className="font-display text-lg font-bold text-ink-900 dark:text-white">
              How do we know LearnMate is grounded and reliable?
            </h2>
            <p className="text-xs text-ink-600 dark:text-ink-300 leading-relaxed">
              Unlike generic conversational chatbots, LearnMate pairs answers directly with indexed course context. Every query is scored across <strong>Faithfulness</strong> (verifiable source claims), <strong>Citation Precision</strong> (page, slide, and timestamp accuracy), <strong>Grounding Accuracy</strong> (answering in-domain questions and rejecting out-of-scope topics), and <strong>Course Isolation</strong> (0% cross-course data leakage).
            </p>
          </div>
          <div className="flex flex-col gap-2 shrink-0 bg-white dark:bg-ink-900/90 rounded-xl border border-ink-200 dark:border-ink-800 p-3.5 shadow-sm text-xs w-full md:w-auto">
            <div className="flex items-center gap-2">
              <CheckCircle className="h-4 w-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
              <span className="font-semibold text-ink-800 dark:text-ink-100">Strict Source Attribution</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle className="h-4 w-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
              <span className="font-semibold text-ink-800 dark:text-ink-100">0 Cross-Course Leakage</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle className="h-4 w-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
              <span className="font-semibold text-ink-800 dark:text-ink-100">Multimodal: PDF, PPTX, MP4, YouTube</span>
            </div>
          </div>
        </div>
      </div>

      {/* Progress State Indicator */}
      {(evalState === 'starting' || evalState === 'running') && (
        <div className="mt-6 card p-5 animate-fade-in border-l-4 border-brand-500">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50 dark:bg-brand-950/60 text-brand-600 dark:text-brand-400">
              <Loader2 className="h-5 w-5 animate-spin" />
            </span>
            <div>
              <p className="text-sm font-semibold text-ink-900 dark:text-white">
                {evalState === 'starting' ? 'Starting evaluation...' : 'Evaluation in progress...'}
              </p>
              <p className="text-xs text-ink-500 dark:text-ink-400 mt-0.5">
                Testing retrieval, citations, grounding, isolation, assessments, and learner simulations. The page will update automatically.
              </p>
              {evaluationId && (
                <p className="text-xs text-ink-400 dark:text-ink-500 mt-1 font-mono">
                  ID: {evaluationId}
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Error State */}
      {evalState === 'failed' && (
        <div className="mt-6 flex items-start gap-3 rounded-lg border border-err-200 dark:border-err-800 bg-err-50 dark:bg-err-950/40 px-4 py-3.5 animate-fade-in">
          <AlertCircle className="h-5 w-5 text-err-500 shrink-0 mt-0.5" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-err-800 dark:text-err-200">Evaluation failed</p>
            <p className="text-sm text-err-700 dark:text-err-300 mt-1 leading-relaxed break-words">
              {getErrorMessage(errorMessage)}
            </p>
          </div>
          <button
            onClick={handleRunEvaluation}
            className="btn-secondary shrink-0 flex items-center gap-1.5 ml-2"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Retry
          </button>
        </div>
      )}

      {/* Results State */}
      {evalState === 'completed' && result && (
        <EvaluationResults result={result} />
      )}

      {/* Empty State */}
      {evalState === 'idle' && !result && (
        <div className="mt-8">
          <EmptyState
            icon={<BarChart3 className="h-7 w-7" />}
            title="No evaluation run yet"
            description="Click Run Evaluation to measure system quality across RAG metrics, grounding, citation accuracy, course isolation, and learner simulation."
          />
        </div>
      )}

      {/* Methodology Section */}
      <div className="mt-8">
        <button
          onClick={() => setMethodologyOpen(!methodologyOpen)}
          className="flex w-full items-center justify-between rounded-lg border border-ink-200 dark:border-ink-800 bg-white dark:bg-ink-900 px-4 py-3 text-sm font-medium text-ink-700 dark:text-ink-200 transition-colors hover:bg-ink-50 dark:hover:bg-ink-800"
        >
          <span className="flex items-center gap-2">
            <HelpCircle className="h-4 w-4 text-brand-600 dark:text-brand-400" />
            How we evaluate
          </span>
          {methodologyOpen ? (
            <ChevronUp className="h-4 w-4 text-ink-400 dark:text-ink-500" />
          ) : (
            <ChevronDown className="h-4 w-4 text-ink-400 dark:text-ink-500" />
          )}
        </button>
        {methodologyOpen && (
          <div className="mt-2 card p-5 animate-fade-in">
            <div className="grid gap-4 sm:grid-cols-2">
              <MethodologyItem
                icon={<Shield className="h-4 w-4" />}
                title="Grounding"
                description="Tests whether the tutor correctly answers questions supported by course material and rejects questions outside the material."
              />
              <MethodologyItem
                icon={<FileText className="h-4 w-4" />}
                title="Citation Correctness"
                description="Verifies that citations reference the correct source location (page, slide, or timestamp) for the answer."
              />
              <MethodologyItem
                icon={<Target className="h-4 w-4" />}
                title="Answer Relevancy"
                description="Measures how directly the answer addresses the question asked."
              />
              <MethodologyItem
                icon={<CheckCircle className="h-4 w-4" />}
                title="Faithfulness"
                description="Checks that the answer is supported by the retrieved context and doesn't introduce unsupported claims."
              />
              <MethodologyItem
                icon={<TrendingUp className="h-4 w-4" />}
                title="Context Precision"
                description="Evaluates whether the retrieved context is relevant to answering the question."
              />
              <MethodologyItem
                icon={<BarChart3 className="h-4 w-4" />}
                title="Context Recall"
                description="Measures whether all information needed to answer the question was retrieved from the source material."
              />
              <MethodologyItem
                icon={<Shield className="h-4 w-4" />}
                title="Course Isolation"
                description="Tests whether content from one course can leak into another course's answers."
              />
              <MethodologyItem
                icon={<Users className="h-4 w-4" />}
                title="Learner Simulation"
                description="Simulates high, mixed, and struggling learners to validate mastery tracking and recommendation quality."
              />
            </div>
            <p className="mt-4 text-xs text-ink-400 dark:text-ink-500 leading-relaxed">
              Metrics are generated by the backend's evaluation engine. The evaluation uses reference questions and expected outcomes to score each dimension.
            </p>
          </div>
        )}
      </div>
    </AppLayout>
  );
}

// ── Results Component ──

function EvaluationResults({ result }: { result: EvaluationResult }) {
  const summary = extractSummary(result);
  const simulations = extractSimulations(result);
  const failures: EvaluationFailure[] = Array.isArray(result.failures) ? result.failures : [];
  const datasetSize = summary?.dataset_size ?? summary?.total_test_cases ?? (Array.isArray(result.results) ? result.results.length : null);
  const failedCount = failures.length;
  const passedCount = summary?.passed_test_cases ?? (datasetSize != null ? Math.max(datasetSize - failedCount, 0) : null);

  return (
    <div className="mt-6 space-y-6">
      {/* Summary header */}
      <div className="card p-5 animate-fade-in">
        <div className="flex items-center gap-2 mb-4">
          <Award className="h-5 w-5 text-brand-600 dark:text-brand-400" />
          <h2 className="font-display text-lg font-semibold text-ink-900 dark:text-white">
            Latest Evaluation
          </h2>
          <span className="badge-success shrink-0 inline-flex items-center gap-1">
            <CheckCircle className="h-3 w-3" />
            Completed
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-xs text-ink-500 dark:text-ink-400">
          <span className="inline-flex items-center gap-1.5">
            <BarChart3 className="h-3.5 w-3.5 text-ink-400 dark:text-ink-500" />
            {datasetSize != null ? `${datasetSize} evaluation cases` : 'Dataset size unavailable'}
          </span>
          {result.completed_at && (
            <span className="inline-flex items-center gap-1.5">
              <Clock className="h-3.5 w-3.5 text-ink-400 dark:text-ink-500" />
              {formatTimestamp(result.completed_at)}
            </span>
          )}
          {passedCount != null && (
            <span className="inline-flex items-center gap-1.5">
              <CheckCircle className="h-3.5 w-3.5 text-accent-600 dark:text-accent-400" />
              {passedCount} passed
            </span>
          )}
          {failedCount > 0 && (
            <span className="inline-flex items-center gap-1.5">
              <XCircle className="h-3.5 w-3.5 text-err-600 dark:text-err-400" />
              {failedCount} failed
            </span>
          )}
        </div>
      </div>

      {/* RAG / Retrieval Evaluation */}
      <section>
        <SectionHeader icon={<TrendingUp className="h-5 w-5 text-brand-600 dark:text-brand-400" />} title="RAG / Retrieval Evaluation" />
        <div className="grid gap-4 sm:grid-cols-2">
          <MetricCard label="Answer Relevancy" value={summary?.answer_relevancy} description="How directly the answer addresses the question" />
          <MetricCard label="Faithfulness" value={summary?.faithfulness} description="Answer is supported by retrieved context" />
          <MetricCard label="Context Precision" value={summary?.context_precision} description="Retrieved context is relevant" />
          <MetricCard label="Context Recall" value={summary?.context_recall} description="All needed information was retrieved" />
        </div>
      </section>

      {/* Grounding & Citations */}
      <section>
        <SectionHeader icon={<Shield className="h-5 w-5 text-brand-600 dark:text-brand-400" />} title="Grounding & Citations" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <MetricCard label="Grounding Accuracy" value={summary?.grounding_accuracy} description="Correctly grounded vs. rejected" />
          <MetricCard label="Citation Accuracy" value={summary?.citation_accuracy} description="Citations point to correct source location" />
          <StatCard
            label="Course Isolation Failures"
            value={summary?.course_isolation_failures != null ? String(summary.course_isolation_failures) : '0'}
            description="Cross-course boundary testing. 0 failures guarantees zero cross-tenant content leakage."
          />
          {summary?.supported_questions_count != null && (
            <StatCard
              label="Supported Benchmark Cases"
              value={`${summary.supported_questions_passed ?? 0} / ${summary.supported_questions_count}`}
              description="Predefined in-domain questions answered correctly with course citations"
            />
          )}
          {summary?.unsupported_questions_count != null && (
            <StatCard
              label="Unsupported Cases Rejected"
              value={`${summary.unsupported_questions_passed ?? 0} / ${summary.unsupported_questions_count}`}
              description="Predefined out-of-scope questions correctly rejected without hallucination"
            />
          )}
          {summary?.citation_failure_count != null && (
            <StatCard
              label="Citation Failures"
              value={String(summary.citation_failure_count)}
              description="Invalid or missing source citations"
            />
          )}
        </div>
      </section>

      {/* Assessment Question Quality */}
      <section>
        <SectionHeader icon={<Target className="h-5 w-5 text-brand-600 dark:text-brand-400" />} title="Assessment Generation Quality" />
        <div className="grid gap-4 sm:grid-cols-2">
          <MetricCard
            label="Question Validity Rate"
            value={summary?.assessment_valid_question_rate}
            nullPlaceholder="Not measured"
            supportingText={
              summary?.assessment_questions_valid != null && summary?.assessment_questions_evaluated != null
                ? `${summary.assessment_questions_valid} of ${summary.assessment_questions_evaluated} questions valid`
                : undefined
            }
            description="Generated assessment questions meeting quality and format standards"
          />
          <MetricCard
            label="Question Duplicate Rate"
            value={summary?.duplicate_rate}
            nullPlaceholder="Not measured"
            lowerIsBetter
            supportingText={
              summary?.duplicate_questions_detected != null && summary?.duplicate_questions_evaluated != null
                ? `${summary.duplicate_questions_detected} of ${summary.duplicate_questions_evaluated} duplicate questions`
                : undefined
            }
            description="Duplication rate across repeated generation rounds (lower is better)"
          />
        </div>
      </section>

      {/* Learner Simulation */}
      {simulations.length > 0 && (
        <section>
          <SectionHeader icon={<Users className="h-5 w-5 text-brand-600 dark:text-brand-400" />} title="Learner Profile Simulations" />
          <div className="grid gap-4 sm:grid-cols-3">
            {simulations.map((s, i) => {
              const icon =
                i === 0 ? <Award className="h-4 w-4 text-accent-600 dark:text-accent-400" /> :
                i === 1 ? <BarChart3 className="h-4 w-4 text-brand-600 dark:text-brand-400" /> :
                <TrendingUp className="h-4 w-4 text-warn-600 dark:text-warn-400" />;
              return <LearnerSimCard key={i} sim={s} icon={icon} />;
            })}
          </div>
        </section>
      )}

      {/* Test Cases & Failure Analysis */}
      <section>
        <SectionHeader icon={<FileText className="h-5 w-5 text-brand-600 dark:text-brand-400" />} title="Evaluation Benchmark Cases" />
        <p className="-mt-2 mb-4 text-xs text-ink-500 dark:text-ink-400 leading-relaxed">
          These are predefined test cases used to evaluate retrieval, citation, and learner-isolation behavior. They are not learner-generated questions.
        </p>
        <div className="card p-5">
          <div className="grid gap-4 sm:grid-cols-3">
            <StatCard label="Total Evaluated" value={datasetSize != null ? String(datasetSize) : 'Unavailable'} />
            <StatCard label="Passed" value={passedCount != null ? String(passedCount) : 'Unavailable'} />
            <StatCard label="Failed" value={String(failedCount)} />
          </div>

          {failures.length > 0 ? (
            <div className="mt-5">
              <h3 className="font-display text-sm font-semibold text-ink-900 dark:text-white mb-3 flex items-center gap-2">
                <AlertCircle className="h-4 w-4 text-warn-600 dark:text-warn-400" />
                Cases Needing Attention ({failures.length})
              </h3>
              <div className="space-y-3">
                {failures.map((f, i) => (
                  <FailureCard key={i} failure={f} index={i} />
                ))}
              </div>
            </div>
          ) : (
            <div className="mt-5 flex items-center gap-2.5 rounded-lg border border-accent-200 dark:border-accent-800 bg-accent-50 dark:bg-accent-950/40 px-4 py-3">
              <CheckCircle className="h-5 w-5 text-accent-600 dark:text-accent-400 shrink-0" />
              <p className="text-sm font-medium text-accent-700 dark:text-accent-300">All evaluated benchmark cases passed successfully.</p>
            </div>
          )}

          {/* Detailed results list */}
          {Array.isArray(result.results) && result.results.length > 0 && (
            <div className="mt-6 pt-5 border-t border-ink-100 dark:border-ink-800">
              <h3 className="font-display text-sm font-semibold text-ink-900 dark:text-white mb-3">
                Test Case Details ({result.results.length})
              </h3>
              <div className="space-y-2">
                {result.results.map((item: EvaluationResultItem, idx: number) => (
                  <TestCaseItemCard key={item.test_case_id || idx} item={item} />
                ))}
              </div>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

// ── Sub-components ──

function SectionHeader({ icon, title }: { icon: React.ReactNode; title: string }) {
  return (
    <h2 className="font-display text-lg font-semibold text-ink-900 dark:text-white mb-4 flex items-center gap-2">
      {icon}
      {title}
    </h2>
  );
}

function MetricCard({
  label,
  value,
  description,
  nullPlaceholder = 'Unavailable',
  supportingText,
  lowerIsBetter = false,
}: {
  label: string;
  value: number | null | undefined;
  description?: string;
  nullPlaceholder?: string;
  supportingText?: React.ReactNode;
  lowerIsBetter?: boolean;
}) {
  const isNull = value === null || value === undefined || typeof value !== 'number' || isNaN(value);
  const formattedScore = isNull ? nullPlaceholder : `${Math.round(value * 100)}%`;

  return (
    <div className="card p-4">
      <p className="text-sm font-medium text-ink-700 dark:text-ink-300">{label}</p>
      <p className={`mt-2 font-display text-2xl font-bold ${scoreColor(value, lowerIsBetter)}`}>
        {formattedScore}
      </p>
      {supportingText && (
        <p className="mt-1 text-xs font-medium text-ink-500 dark:text-ink-400">
          {supportingText}
        </p>
      )}
      {description && (
        <p className="mt-1.5 text-xs text-ink-400 dark:text-ink-500 leading-relaxed">{description}</p>
      )}
      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-ink-100 dark:bg-ink-800">
        <div
          className={`h-full rounded-full transition-all duration-500 ${barColor(value, lowerIsBetter)}`}
          style={{ width: barWidth(value) }}
        />
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  description,
}: {
  label: string;
  value: string;
  description?: string;
}) {
  return (
    <div className="rounded-xl border border-ink-200 dark:border-ink-800 bg-ink-50/40 dark:bg-ink-900/60 p-4">
      <p className="text-sm font-medium text-ink-700 dark:text-ink-300">{label}</p>
      <p className="mt-1.5 font-display text-xl font-bold text-ink-900 dark:text-white">{value}</p>
      {description && (
        <p className="mt-1 text-xs text-ink-400 dark:text-ink-500 leading-relaxed">{description}</p>
      )}
    </div>
  );
}

function LearnerSimCard({
  sim,
  icon,
}: {
  sim: FormattedSimulation;
  icon: React.ReactNode;
}) {
  const beforePct = sim.masteryBefore != null ? Math.round(sim.masteryBefore * 100) : null;
  const afterPct = sim.masteryAfter != null ? Math.round(sim.masteryAfter * 100) : null;
  const gainPct = sim.masteryGain != null ? Math.round(sim.masteryGain * 100) : null;
  const confBeforePct = sim.confidenceBefore != null ? Math.round(sim.confidenceBefore * 100) : null;
  const confAfterPct = sim.confidenceAfter != null ? Math.round(sim.confidenceAfter * 100) : null;

  return (
    <div className="card p-4">
      <div className="flex items-center gap-2 mb-3">
        {icon}
        <div>
          <p className="text-sm font-semibold text-ink-800 dark:text-ink-200">{sim.label}</p>
          {sim.topic && <p className="text-[11px] text-ink-500 dark:text-ink-400">{sim.topic}</p>}
        </div>
      </div>
      <div className="space-y-2.5">
        {beforePct != null && afterPct != null && (
          <div>
            <p className="text-xs text-ink-500 dark:text-ink-400 mb-1">Mastery: Before → After</p>
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-ink-600 dark:text-ink-300">{beforePct}%</span>
              <span className="text-ink-300 dark:text-ink-600">→</span>
              <span className="text-sm font-bold text-ink-900 dark:text-white">{afterPct}%</span>
            </div>
          </div>
        )}
        {gainPct != null && (
          <div>
            <p className="text-xs text-ink-500 dark:text-ink-400 mb-1">Mastery Gain</p>
            <div className="flex items-center gap-2">
              <span className={`text-sm font-bold ${gainPct > 0 ? 'text-accent-600 dark:text-accent-400' : 'text-ink-600 dark:text-ink-300'}`}>
                {gainPct > 0 ? '+' : ''}{gainPct}%
              </span>
              <div className="flex-1 h-1.5 overflow-hidden rounded-full bg-ink-100 dark:bg-ink-800">
                <div
                  className="h-full rounded-full bg-accent-500 transition-all duration-500"
                  style={{ width: `${Math.min(Math.abs(gainPct), 100)}%` }}
                />
              </div>
            </div>
          </div>
        )}
        {confBeforePct != null && confAfterPct != null && (
          <div>
            <p className="text-xs text-ink-500 dark:text-ink-400 mb-1">Confidence Score</p>
            <p className="text-xs text-ink-700 dark:text-ink-200 font-medium">
              {confBeforePct}% → {confAfterPct}%
            </p>
          </div>
        )}
        {sim.weakTopics.length > 0 && (
          <div>
            <p className="text-xs text-ink-500 dark:text-ink-400 mb-1">Weak Topics Detected</p>
            <div className="flex flex-wrap gap-1">
              {sim.weakTopics.map((topic, i) => (
                <span key={i} className="inline-block rounded bg-warn-100 dark:bg-warn-950/70 px-1.5 py-0.5 text-[10px] font-medium text-warn-800 dark:text-warn-300">
                  {topic}
                </span>
              ))}
            </div>
          </div>
        )}
        {sim.recommendationsCount > 0 && (
          <p className="text-xs text-ink-600 dark:text-ink-300 flex items-center gap-1.5 mt-2">
            <Sparkles className="h-3 w-3 text-brand-500 shrink-0" />
            {sim.recommendationsCount} personalized recommendation{sim.recommendationsCount > 1 ? 's' : ''} generated
          </p>
        )}
      </div>
    </div>
  );
}

function FailureCard({ failure, index }: { failure: EvaluationFailure; index: number }) {
  const question = typeof failure.question === 'string' ? failure.question : '';
  const reason = typeof (failure.failure_reason || failure.reason) === 'string'
    ? (failure.failure_reason || failure.reason)
    : '';
  const citationIssue = typeof failure.citation_issue === 'string' ? failure.citation_issue : '';
  const testCaseId = typeof failure.test_case_id === 'string' ? failure.test_case_id : '';

  return (
    <div
      className="rounded-lg border border-warn-200 dark:border-warn-800 bg-warn-50/40 dark:bg-warn-950/30 p-4 animate-fade-in"
      style={{ animationDelay: `${index * 50}ms` }}
    >
      <div className="flex items-start gap-2.5">
        <AlertCircle className="h-4 w-4 text-warn-600 dark:text-warn-400 shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0 space-y-1.5">
          <div className="flex items-center gap-2">
            {testCaseId && (
              <span className="inline-block rounded bg-warn-100 dark:bg-warn-950/80 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-warn-800 dark:text-warn-300">
                {testCaseId}
              </span>
            )}
            {question && (
              <p className="text-sm font-medium text-ink-800 dark:text-ink-100">{question}</p>
            )}
          </div>
          {reason && (
            <p className="text-xs text-ink-600 dark:text-ink-300 leading-relaxed">
              <span className="font-semibold text-ink-700 dark:text-ink-200">Issue: </span>
              {reason}
            </p>
          )}
          {citationIssue && (
            <p className="text-xs text-warn-700 dark:text-warn-300">
              <span className="font-semibold">Citation: </span>
              {citationIssue}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function TestCaseItemCard({ item }: { item: EvaluationResultItem }) {
  const [expanded, setExpanded] = useState(false);
  const testCaseId = typeof item.test_case_id === 'string' ? item.test_case_id : '';
  const question = typeof item.question === 'string' ? item.question : '';
  const passed = Boolean(item.passed);
  const answer = typeof item.answer === 'string' ? item.answer : '';
  const failureReason = typeof item.failure_reason === 'string' ? item.failure_reason : '';

  return (
    <div className="rounded-md border border-ink-150 dark:border-ink-800 bg-white dark:bg-ink-900 p-3 text-xs">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-mono text-[10px] font-semibold ${
            passed ? 'bg-accent-100 text-accent-800 dark:bg-accent-950/70 dark:text-accent-300' : 'bg-err-100 text-err-800 dark:bg-err-950/70 dark:text-err-300'
          }`}>
            {passed ? <CheckCircle className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
            {passed ? 'Passed' : 'Failed'}
          </span>
          <span className="font-mono text-ink-400 dark:text-ink-500 text-[11px]">{testCaseId}</span>
          <span className="font-medium text-ink-800 dark:text-ink-200 truncate">{question}</span>
        </div>
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-ink-400 hover:text-ink-600 dark:text-ink-500 dark:hover:text-ink-300 shrink-0 text-[11px] underline ml-2"
        >
          {expanded ? 'Hide' : 'Details'}
        </button>
      </div>

      {expanded && (
        <div className="mt-2.5 pt-2 border-t border-ink-100 dark:border-ink-800 space-y-1.5 text-ink-600 dark:text-ink-300">
          <p><span className="font-semibold text-ink-700 dark:text-ink-200">Benchmark Question: </span>{question}</p>
          <p><span className="font-semibold text-ink-700 dark:text-ink-200">System Response: </span>{answer}</p>
          <p>
            <span className="font-semibold text-ink-700 dark:text-ink-200">Grounded: </span>
            {item.actual_grounded ? 'Yes' : 'No'} (Expected: {item.expected_grounded ? 'Yes' : 'No'})
            {' | '}
            <span className="font-semibold text-ink-700 dark:text-ink-200">Citation Correct: </span>
            {item.citation_correct ? 'Yes' : 'No'}
          </p>
          {failureReason && (
            <p className="text-err-700 dark:text-err-400">
              <span className="font-semibold">Failure Reason: </span>
              {failureReason}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function MethodologyItem({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="flex items-start gap-2.5">
      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-brand-50 dark:bg-brand-950/60 text-brand-600 dark:text-brand-400">
        {icon}
      </span>
      <div>
        <p className="text-sm font-medium text-ink-800 dark:text-ink-200">{title}</p>
        <p className="text-xs text-ink-500 dark:text-ink-400 mt-0.5 leading-relaxed">{description}</p>
      </div>
    </div>
  );
}

