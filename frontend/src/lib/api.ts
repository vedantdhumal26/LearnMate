import type {
  Course,
  Source,
  TutorResponse,
  CreateCoursePayload,
  ApiError,
  Assessment,
  GenerateAssessmentPayload,
  SubmitAssessmentPayload,
  AssessmentResult,
  LearnerMastery,
  LearnerSummary,
  LearnerRecommendations,
  StudyPlanResponse,
  EvaluationRun,
  EvaluationStatus,
  EvaluationResult,
  EvaluationRunRequest,
  User,
  AuthResponse,
  LoginRequest,
  SignupRequest,
  YouTubeSourceResponse,
  UpdateUserPayload,
  UpdateCoursePayload,
  UploadResponse,
} from '@/types';
import { tokenStorage } from './auth-token';

const envApiUrl = import.meta.env.VITE_API_URL;
const API_BASE = (envApiUrl !== undefined && envApiUrl !== null && envApiUrl !== '' ? envApiUrl : '').replace(/\/+$/, '');

function buildUrl(path: string): string {
  const normalized = path.startsWith('/') ? path : `/${path}`;
  return `${API_BASE}${normalized}`;
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  timeoutMs = 60000,
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  if (options.signal) {
    if (options.signal.aborted) {
      controller.abort();
    } else {
      options.signal.addEventListener('abort', () => controller.abort(), { once: true });
    }
  }

  const isPublicAuth =
    path === '/api/auth/login' ||
    path === '/api/auth/signup' ||
    path === '/health';

  const token = tokenStorage.getToken();
  const headers: Record<string, string> = {
    ...(options.body instanceof FormData
      ? {}
      : { 'Content-Type': 'application/json' }),
    ...((options.headers as Record<string, string>) || {}),
  };

  // Automatically attach Bearer token to authenticated requests
  if (!isPublicAuth && token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(buildUrl(path), {
      ...options,
      headers,
      signal: controller.signal,
    });
  } catch (err: unknown) {
    clearTimeout(timer);
    if (controller.signal.aborted || (err instanceof Error && err.name === 'AbortError')) {
      const timeoutErr: ApiError = new Error('AI service timed out. Please try again.');
      timeoutErr.status = 504;
      timeoutErr.detail = 'AI service timed out. Please try again.';
      throw timeoutErr;
    }
    const connectErr: ApiError = new Error(
      'Unable to connect to the backend service. Please make sure the backend is running.',
    );
    connectErr.status = 0;
    connectErr.detail = connectErr.message;
    throw connectErr;
  } finally {
    clearTimeout(timer);
  }

  if (!response.ok) {
    // Centrally handle 401 Unauthorized for non-public requests
    if (response.status === 401 && !isPublicAuth) {
      tokenStorage.notifyUnauthorized();
    }

    let rawDetail: unknown = '';
    try {
      const body = await response.json();
      rawDetail =
        (body as Record<string, unknown>)?.detail ??
        (body as Record<string, unknown>)?.message ??
        '';
    } catch {
      /* response had no JSON body */
    }

    let safeMessage: string;
    if (response.status === 401) {
      safeMessage = getErrorMessage(rawDetail) || 'Incorrect email or password, or session expired.';
    } else if (response.status === 429) {
      safeMessage = 'The AI service is temporarily rate-limited. Please wait a few moments and try again.';
    } else if (response.status === 504) {
      safeMessage = 'AI service timed out. Please try again.';
    } else {
      safeMessage = getErrorMessage(rawDetail) || `Request failed with status ${response.status}.`;
    }

    const err: ApiError = new Error(safeMessage);
    err.status = response.status;
    err.detail = safeMessage;
    err.rawDetail = rawDetail;
    throw err;
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  try {
    return (await response.json()) as T;
  } catch {
    return undefined as T;
  }
}

export const api = {
  health(): Promise<{ status: string }> {
    return request('/health');
  },

  signup(payload: SignupRequest): Promise<AuthResponse> {
    return request('/api/auth/signup', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  login(payload: LoginRequest): Promise<AuthResponse> {
    return request('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  getMe(): Promise<User> {
    return request('/api/auth/me');
  },

  updateMe(payload: UpdateUserPayload): Promise<User> {
    return request('/api/auth/me', {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  },

  getCourses(): Promise<Course[]> {
    return request('/api/courses');
  },

  createCourse(payload: CreateCoursePayload): Promise<Course> {
    return request('/api/courses', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  getCourse(courseId: string): Promise<Course> {
    return request(`/api/courses/${encodeURIComponent(courseId)}`);
  },

  updateCourse(courseId: string, payload: UpdateCoursePayload): Promise<Course> {
    return request(`/api/courses/${encodeURIComponent(courseId)}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  },

  deleteCourse(courseId: string): Promise<void> {
    return request(`/api/courses/${encodeURIComponent(courseId)}`, {
      method: 'DELETE',
    });
  },

  deleteCourseMaterial(courseId: string, materialId: string): Promise<void> {
    return request(
      `/api/courses/${encodeURIComponent(courseId)}/materials/${encodeURIComponent(materialId)}`,
      {
        method: 'DELETE',
      },
    );
  },

  uploadFile(courseId: string, file: File): Promise<UploadResponse> {
    const formData = new FormData();
    formData.append('file', file);
    return request(`/api/courses/${encodeURIComponent(courseId)}/upload`, {
      method: 'POST',
      body: formData,
    });
  },

  addYouTubeSource(courseId: string, url: string): Promise<YouTubeSourceResponse> {
    return request(`/api/courses/${encodeURIComponent(courseId)}/youtube`, {
      method: 'POST',
      body: JSON.stringify({ url }),
    });
  },

  getUploadStatus(courseId: string, sourceId: string): Promise<Source> {
    return request(
      `/api/courses/${encodeURIComponent(courseId)}/uploads/${encodeURIComponent(sourceId)}`,
    );
  },

  async sendTutorMessage(
    courseId: string,
    message: string,
    signal?: AbortSignal,
    timeoutMs = 60000,
  ): Promise<TutorResponse> {
    console.log('[TUTOR REQUEST START]', { course_id: courseId, message });
    try {
      const res = await request<TutorResponse>(
        '/api/tutor/chat',
        {
          method: 'POST',
          body: JSON.stringify({ course_id: courseId, message }),
          signal,
        },
        timeoutMs,
      );
      console.log('[TUTOR RESPONSE STATUS]', 200);
      console.log('[TUTOR RESPONSE BODY]', res);
      return res;
    } catch (err: unknown) {
      const status = (err as ApiError)?.status ?? 'ERROR';
      console.log('[TUTOR RESPONSE STATUS]', status);
      console.log('[TUTOR RESPONSE BODY]', (err as ApiError)?.detail || (err as Error)?.message);
      console.error('[TUTOR CAUGHT ERROR]', err);
      throw err;
    } finally {
      console.log('[TUTOR REQUEST END]');
    }
  },

  async generateAssessment(
    payload: GenerateAssessmentPayload,
    signal?: AbortSignal,
    timeoutMs = 60000,
  ): Promise<Assessment> {
    console.log('[ASSESSMENT REQUEST START]', payload);
    try {
      const res = await request<Assessment>(
        '/api/assessments/generate',
        {
          method: 'POST',
          body: JSON.stringify(payload),
          signal,
        },
        timeoutMs,
      );
      console.log('[ASSESSMENT RESPONSE STATUS]', 201);
      console.log('[ASSESSMENT RESPONSE BODY]', res);
      return res;
    } catch (err: unknown) {
      const status = (err as ApiError)?.status ?? 'ERROR';
      console.log('[ASSESSMENT RESPONSE STATUS]', status);
      console.log('[ASSESSMENT RESPONSE BODY]', (err as ApiError)?.detail || (err as Error)?.message);
      console.error('[ASSESSMENT CAUGHT ERROR]', err);
      throw err;
    } finally {
      console.log('[ASSESSMENT REQUEST END]');
    }
  },

  getAssessment(assessmentId: string): Promise<Assessment> {
    return request(`/api/assessments/${encodeURIComponent(assessmentId)}`);
  },

  submitAssessment(
    assessmentId: string,
    payload: SubmitAssessmentPayload,
  ): Promise<AssessmentResult> {
    return request(`/api/assessments/${encodeURIComponent(assessmentId)}/submit`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  getLearnerMastery(studentId?: string, courseId?: string): Promise<LearnerMastery> {
    const id = studentId || tokenStorage.getUser()?.id || '';
    const cId = courseId || '';
    return request(`/api/learner/${encodeURIComponent(id)}/courses/${encodeURIComponent(cId)}/mastery`);
  },

  getLearnerSummary(studentId?: string, courseId?: string): Promise<LearnerSummary> {
    const id = studentId || tokenStorage.getUser()?.id || '';
    const cId = courseId || '';
    return request(`/api/learner/${encodeURIComponent(id)}/courses/${encodeURIComponent(cId)}/summary`);
  },

  getLearnerRecommendations(studentId?: string, courseId?: string): Promise<LearnerRecommendations> {
    const id = studentId || tokenStorage.getUser()?.id || '';
    const cId = courseId || '';
    return request(`/api/learner/${encodeURIComponent(id)}/courses/${encodeURIComponent(cId)}/recommendations`);
  },

  getStudyPlan(studentId?: string, courseId?: string): Promise<StudyPlanResponse> {
    const id = studentId || tokenStorage.getUser()?.id || '';
    const cId = courseId || '';
    return request(`/api/learner/${encodeURIComponent(id)}/courses/${encodeURIComponent(cId)}/study-plan`);
  },

  runEvaluation(payload?: EvaluationRunRequest): Promise<EvaluationRun> {
    const body: Record<string, unknown> = {
      name: payload?.name ?? 'LearnMate System Evaluation',
      run_learner_simulations: payload?.run_learner_simulations ?? true,
      run_assessment_eval: payload?.run_assessment_eval ?? true,
      sync: payload?.sync ?? false,
    };
    if (payload?.course_id) body.course_id = payload.course_id;
    if (payload?.dataset_path) body.dataset_path = payload.dataset_path;
    if (payload?.dataset) body.dataset = payload.dataset;

    return request('/api/evaluation/run', {
      method: 'POST',
      body: JSON.stringify(body),
    });
  },

  getEvaluationStatus(evaluationId: string): Promise<EvaluationStatus> {
    return request(`/api/evaluation/${encodeURIComponent(evaluationId)}`);
  },

  getEvaluationResults(evaluationId: string): Promise<EvaluationResult> {
    return request(`/api/evaluation/${encodeURIComponent(evaluationId)}/results`);
  },
};

/** Wraps sendTutorMessage with a timeout via AbortController. */
export function sendTutorMessageWithTimeout(
  courseId: string,
  message: string,
  timeoutMs = 60000,
): { promise: Promise<TutorResponse>; cancel: () => void } {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  const promise = api
    .sendTutorMessage(courseId, message, controller.signal)
    .finally(() => clearTimeout(timer))
    .catch((err: ApiError) => {
      if (err.name === 'AbortError' || controller.signal.aborted) {
        const e: ApiError = new Error(
          'The tutor is taking too long to respond. Please try again.',
        );
        e.status = 408;
        throw e;
      }
      throw err;
    });

  return { promise, cancel: () => controller.abort() };
}

export function isApiError(e: unknown): e is ApiError {
  return e instanceof Error && 'status' in e;
}

/**
 * Safely extracts a human-readable error string from any error shape.
 * Never returns an object, array, or undefined/null.
 */
export function getErrorMessage(error: unknown): string {
  if (error == null) {
    return 'An unexpected error occurred. Please try again.';
  }

  // String
  if (typeof error === 'string') {
    return error.trim() || 'An unexpected error occurred. Please try again.';
  }

  // Array (e.g. FastAPI validation list: [{ loc, msg, type, input }])
  if (Array.isArray(error)) {
    const messages = error
      .map((item) => {
        if (typeof item === 'string') return item;
        if (item && typeof item === 'object') {
          const dict = item as Record<string, unknown>;
          if (typeof dict.msg === 'string') {
            const locList = Array.isArray(dict.loc)
              ? dict.loc.filter((part) => part !== 'body').join('.')
              : '';
            return locList ? `${locList}: ${dict.msg}` : dict.msg;
          }
          if (typeof dict.detail === 'string') return dict.detail;
          if (typeof dict.message === 'string') return dict.message;
        }
        return getErrorMessage(item);
      })
      .filter((s): s is string => typeof s === 'string' && s.length > 0);

    return messages.length > 0
      ? messages.join('; ')
      : 'Validation error occurred. Please check your input.';
  }

  // Object
  if (typeof error === 'object') {
    const obj = error as Record<string, unknown>;

    // FastAPI single validation item: { loc, msg, type }
    if ('msg' in obj && typeof obj.msg === 'string') {
      const locList = Array.isArray(obj.loc)
        ? obj.loc.filter((part) => part !== 'body').join('.')
        : '';
      return locList ? `${locList}: ${obj.msg}` : obj.msg;
    }

    // ApiError
    if (isApiError(error)) {
      if (error.status === 0) {
        return 'Unable to connect to the backend service. Please make sure the backend is running.';
      }
      if (error.status === 429) {
        return 'AI service is temporarily busy. Please try again.';
      }
      if (error.status === 504) {
        return 'AI service timed out. Please try again.';
      }
      if (error.status === 401) {
        return error.detail || error.message || 'Incorrect email or password, or session expired.';
      }
      if (error.status === 422) {
        const raw = error.rawDetail;
        const msg = raw ? getErrorMessage(raw) : error.message;
        return `Request validation failed: ${msg}`;
      }
      if (error.status === 404) {
        return error.detail || error.message || 'The requested resource was not found.';
      }
      if (error.status === 400) {
        return error.detail || error.message || 'The request was invalid. Please check your input.';
      }
      if (error.status && error.status >= 500) {
        return error.detail || 'Something went wrong on the server. Please try again.';
      }
      if (error.detail && typeof error.detail === 'string') {
        return error.detail;
      }
      return error.message || 'Request failed. Please try again.';
    }

    // Object with 'detail'
    if ('detail' in obj && obj.detail != null) {
      if (typeof obj.detail === 'string') {
        return obj.detail;
      }
      return getErrorMessage(obj.detail);
    }

    // Standard Error
    if (error instanceof Error) {
      return error.message || 'An unexpected error occurred.';
    }

    // Object with 'message'
    if ('message' in obj && typeof obj.message === 'string') {
      return obj.message;
    }

    return 'An unexpected error occurred. Please try again.';
  }

  return String(error);
}

/**
 * Returns the authenticated user's ID.
 * Demo student ID 'student-demo-001' has been permanently removed.
 */
export function getStudentId(): string {
  return tokenStorage.getUser()?.id || '';
}
