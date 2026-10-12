import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  ArrowLeft,
  BookOpen,
  FileText,
  Presentation,
  Video,
  Youtube,
  Sparkles,
  Loader2,
  AlertCircle,
  Calendar,
  Clock,
  CheckCircle,
  XCircle,
  Upload,
  BarChart3,
  TrendingUp,
  ExternalLink,
} from 'lucide-react';
import { AppLayout } from '@/layouts/AppLayout';
import { UploadZone } from '@/components/UploadZone';
import { ErrorState } from '@/components/ErrorState';
import { api, getErrorMessage } from '@/lib/api';
import { getModality } from '@/components/CitationCard';
import type { Course, Source } from '@/types';

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString('en-US', {
      month: 'long',
      day: 'numeric',
      year: 'numeric',
    });
  } catch {
    return iso;
  }
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${String(secs).padStart(2, '0')}`;
}

type ProcessingStatus = 'pending' | 'processing' | 'completed' | 'ready' | 'failed' | string;

function StatusBadge({ status }: { status: ProcessingStatus }) {
  const s = status.toLowerCase();
  if (s === 'completed' || s === 'ready')
    return (
      <span className="badge-success">
        <CheckCircle className="h-3 w-3" />
        Ready
      </span>
    );
  if (s === 'failed')
    return (
      <span className="badge-error">
        <XCircle className="h-3 w-3" />
        Failed
      </span>
    );
  if (s === 'processing' || s === 'pending')
    return (
      <span className="badge-warn">
        <Loader2 className="h-3 w-3 animate-spin" />
        {s === 'pending' ? 'Uploading' : 'Processing'}
      </span>
    );
  return <span className="badge-neutral">{status}</span>;
}

function SourceIcon({ fileName, sourceType }: { fileName: string; sourceType?: string }) {
  const modality = getModality(fileName, sourceType);
  if (modality === 'youtube') return <Youtube className="h-5 w-5" />;
  if (modality === 'pptx') return <Presentation className="h-5 w-5" />;
  if (modality === 'video') return <Video className="h-5 w-5" />;
  return <FileText className="h-5 w-5" />;
}

function SourceModalityBadge({ fileName, sourceType }: { fileName: string; sourceType?: string }) {
  const modality = getModality(fileName, sourceType);
  if (modality === 'youtube') {
    return (
      <span className="inline-flex items-center gap-1 rounded bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-700">
        <Youtube className="h-3 w-3" />
        YouTube
      </span>
    );
  }
  const label = modality === 'pptx' ? 'Slides' : modality === 'video' ? 'Video' : 'PDF';
  return <span className="badge-neutral shrink-0">{label}</span>;
}

type FilterTab = 'all' | 'pdf' | 'pptx' | 'video' | 'youtube';

function sourceMatchesFilter(src: Source, filter: FilterTab): boolean {
  if (filter === 'all') return true;
  return getModality(src.file_name, src.source_type) === filter;
}

export function CoursePage() {
  const { courseId } = useParams<{ courseId: string }>();
  const [course, setCourse] = useState<Course | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState<FilterTab>('all');
  const [sourceOption, setSourceOption] = useState<'upload' | 'youtube'>('upload');
  const [youtubeUrl, setYoutubeUrl] = useState('');
  const [youtubeLoading, setYoutubeLoading] = useState(false);
  const [youtubeError, setYoutubeError] = useState('');
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    if (!courseId) return;
    setLoading(true);
    setError('');
    try {
      const data = await api.getCourse(courseId);
      setCourse(data);
      setSources(data.sources ?? []);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [courseId]);

  useEffect(() => {
    load();
  }, [load]);

  // Poll for source processing status updates
  useEffect(() => {
    const hasProcessing = sources.some(
      (s) =>
        s.processing_status === 'processing' || s.processing_status === 'pending',
    );

    if (!hasProcessing || !courseId) {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      return;
    }

    pollRef.current = setInterval(async () => {
      const processing = sources.filter(
        (s) =>
          s.processing_status === 'processing' ||
          s.processing_status === 'pending',
      );
      for (const src of processing) {
        try {
          const updated = await api.getUploadStatus(courseId, src.id);
          setSources((prev) =>
            prev.map((s) => (s.id === src.id ? updated : s)),
          );
        } catch {
          // silently keep polling
        }
      }
    }, 3000);

    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [sources, courseId]);

  const handleUpload = useCallback(
    async (file: File) => {
      if (!courseId) return;
      const newSource = await api.uploadFile(courseId, file);
      setSources((prev) => [...prev, newSource]);
    },
    [courseId],
  );

  const handleYouTubeSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!courseId || !youtubeUrl.trim()) return;

    setYoutubeLoading(true);
    setYoutubeError('');

    try {
      const newSource = await api.addYouTubeSource(courseId, youtubeUrl.trim());
      setSources((prev) => {
        const exists = prev.some((s) => s.id === newSource.id);
        if (exists) {
          return prev.map((s) => (s.id === newSource.id ? newSource : s));
        }
        return [...prev, newSource];
      });
      setYoutubeUrl('');
      // Switch filter to all or youtube to see the new source
      setFilter('youtube');
    } catch (err: any) {
      setYoutubeError(getErrorMessage(err));
    } finally {
      setYoutubeLoading(false);
    }
  };

  if (loading) {
    return (
      <AppLayout>
        <div className="flex items-center gap-2 text-ink-500">
          <Loader2 className="h-5 w-5 animate-spin" />
          Loading course...
        </div>
      </AppLayout>
    );
  }

  if (error && !course) {
    return (
      <AppLayout>
        <ErrorState message={error} onRetry={load} />
      </AppLayout>
    );
  }

  if (!course) {
    return (
      <AppLayout>
        <ErrorState message="Course not found." />
      </AppLayout>
    );
  }

  const filteredSources = sources.filter((s) => sourceMatchesFilter(s, filter));
  const pdfCount = sources.filter((s) => getModality(s.file_name, s.source_type) === 'pdf').length;
  const pptxCount = sources.filter((s) => getModality(s.file_name, s.source_type) === 'pptx').length;
  const videoCount = sources.filter((s) => getModality(s.file_name, s.source_type) === 'video').length;
  const youtubeCount = sources.filter((s) => getModality(s.file_name, s.source_type) === 'youtube').length;

  return (
    <AppLayout>
      <Link
        to="/dashboard"
        className="inline-flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-700 transition-colors mb-6"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Dashboard
      </Link>

      {/* Course Header */}
      <div className="card p-6">
        <div className="flex items-start gap-4">
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-brand-600 text-white">
            <BookOpen className="h-6 w-6" />
          </span>
          <div className="flex-1 min-w-0">
            <h1 className="font-display text-2xl font-bold tracking-tight text-ink-900">
              {course.title}
            </h1>
            {course.description && (
              <p className="mt-2 text-sm leading-relaxed text-ink-500">
                {course.description}
              </p>
            )}
            <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-ink-500">
              <span className="inline-flex items-center gap-1.5">
                <Calendar className="h-3.5 w-3.5" />
                Created {formatDate(course.created_at)}
              </span>
              <span className="inline-flex items-center gap-1.5">
                <FileText className="h-3.5 w-3.5" />
                {sources.length} source{sources.length !== 1 ? 's' : ''}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Course Materials */}
      <section className="mt-8">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-display text-lg font-semibold text-ink-900">
            Course Materials
          </h2>
          <div className="flex items-center gap-1.5 text-xs text-ink-400">
            <FileText className="h-3.5 w-3.5" />
            <span>PDF</span>
            <span className="text-ink-200">•</span>
            <Presentation className="h-3.5 w-3.5" />
            <span>PPTX</span>
            <span className="text-ink-200">•</span>
            <Video className="h-3.5 w-3.5" />
            <span>MP4</span>
            <span className="text-ink-200">•</span>
            <Youtube className="h-3.5 w-3.5 text-red-600" />
            <span>YouTube</span>
          </div>
        </div>

        {/* Source Mode Toggle: Upload File vs Add YouTube Link */}
        <div className="mb-3 flex items-center gap-2 border-b border-ink-200 pb-2">
          <button
            type="button"
            onClick={() => setSourceOption('upload')}
            className={`inline-flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-semibold transition-colors ${
              sourceOption === 'upload'
                ? 'bg-ink-900 text-white'
                : 'bg-ink-100 text-ink-600 hover:bg-ink-200'
            }`}
          >
            <Upload className="h-3.5 w-3.5" />
            Upload File
          </button>
          <button
            type="button"
            onClick={() => setSourceOption('youtube')}
            className={`inline-flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-semibold transition-colors ${
              sourceOption === 'youtube'
                ? 'bg-red-600 text-white'
                : 'bg-red-50 text-red-700 hover:bg-red-100'
            }`}
          >
            <Youtube className="h-3.5 w-3.5" />
            Add YouTube Link
          </button>
        </div>

        {sourceOption === 'upload' ? (
          <UploadZone onUpload={handleUpload} />
        ) : (
          <div className="card p-5 border-dashed border-2 border-red-200 bg-red-50/20 animate-fade-in">
            <div className="flex items-center gap-2 mb-2">
              <Youtube className="h-5 w-5 text-red-600" />
              <h3 className="text-sm font-semibold text-ink-900">Add YouTube Video Source</h3>
            </div>
            <p className="text-xs text-ink-500 mb-4">
              Paste a public YouTube link (watch, youtu.be, or embed). Available captions and transcripts will be parsed and indexed with exact timestamp citations.
            </p>
            <form onSubmit={handleYouTubeSubmit} className="space-y-3">
              <div className="flex gap-2">
                <input
                  type="url"
                  value={youtubeUrl}
                  onChange={(e) => {
                    setYoutubeUrl(e.target.value);
                    setYoutubeError('');
                  }}
                  placeholder="https://www.youtube.com/watch?v=... or https://youtu.be/..."
                  className="w-full rounded-lg border border-ink-300 bg-white px-3.5 py-2.5 text-sm text-ink-900 placeholder:text-ink-400 focus:border-red-500 focus:outline-none focus:ring-2 focus:ring-red-500/20"
                  disabled={youtubeLoading}
                  required
                />
                <button
                  type="submit"
                  disabled={youtubeLoading || !youtubeUrl.trim()}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-red-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-red-700 disabled:opacity-50 transition-colors shrink-0"
                >
                  {youtubeLoading ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Processing...
                    </>
                  ) : (
                    <>
                      <Youtube className="h-4 w-4" />
                      Add YouTube Link
                    </>
                  )}
                </button>
              </div>
              {youtubeError && (
                <div className="flex items-start gap-2 rounded-lg bg-red-50 border border-red-200 p-2.5 text-xs text-red-700">
                  <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                  <span>{youtubeError}</span>
                </div>
              )}
            </form>
          </div>
        )}

        {/* Source filters: All | PDF | Slides | Video | YouTube */}
        {sources.length > 0 && (
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <FilterButton label="All" count={sources.length} active={filter === 'all'} onClick={() => setFilter('all')} />
            <FilterButton label="PDF" icon={<FileText className="h-3.5 w-3.5" />} count={pdfCount} active={filter === 'pdf'} onClick={() => setFilter('pdf')} />
            <FilterButton label="Slides" icon={<Presentation className="h-3.5 w-3.5" />} count={pptxCount} active={filter === 'pptx'} onClick={() => setFilter('pptx')} />
            <FilterButton label="Video" icon={<Video className="h-3.5 w-3.5" />} count={videoCount} active={filter === 'video'} onClick={() => setFilter('video')} />
            <FilterButton label="YouTube" icon={<Youtube className="h-3.5 w-3.5 text-red-600" />} count={youtubeCount} active={filter === 'youtube'} onClick={() => setFilter('youtube')} />
          </div>
        )}

        {filteredSources.length > 0 && (
          <div className="mt-4 space-y-3">
            {filteredSources.map((src) => {
              const modality = getModality(src.file_name, src.source_type);
              const durationVal = src.duration_seconds || src.duration;
              const titleText = src.title || src.file_name;
              return (
                <div
                  key={src.id}
                  className="card p-4 animate-fade-in"
                >
                  <div className="flex items-start gap-3">
                    <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${
                      modality === 'youtube'
                        ? 'bg-red-50 text-red-600 border border-red-200'
                        : modality === 'video'
                        ? 'bg-brand-50 text-brand-600'
                        : modality === 'pptx'
                        ? 'bg-accent-50 text-accent-600'
                        : 'bg-ink-100 text-ink-500'
                    }`}>
                      <SourceIcon fileName={src.file_name} sourceType={src.source_type} />
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-center gap-2 min-w-0">
                          <p className="text-sm font-medium text-ink-800 truncate" title={titleText}>
                            {titleText}
                          </p>
                          <SourceModalityBadge fileName={src.file_name} sourceType={src.source_type} />
                        </div>
                        <StatusBadge status={src.processing_status} />
                      </div>
                      <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-500">
                        <span className="inline-flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {formatTime(src.created_at)}
                        </span>
                        {/* Modality-specific metadata */}
                        {modality === 'pptx' && src.slide_count != null && (
                          <span>{src.slide_count} slide{src.slide_count !== 1 ? 's' : ''}</span>
                        )}
                        {modality === 'pptx' && src.visual_count != null && (
                          <span>{src.visual_count} visual{src.visual_count !== 1 ? 's' : ''}</span>
                        )}
                        {modality === 'video' && durationVal != null && (
                          <span>{formatDuration(durationVal)} duration</span>
                        )}
                        {modality === 'video' && src.segment_count != null && (
                          <span>{src.segment_count} segment{src.segment_count !== 1 ? 's' : ''}</span>
                        )}
                        {modality === 'youtube' && durationVal != null && (
                          <span>{formatDuration(durationVal)} duration</span>
                        )}
                        {modality === 'youtube' && (
                          <span className="text-red-600 font-medium">YouTube Video Source</span>
                        )}
                        {modality === 'youtube' && src.canonical_url && (
                          <a
                            href={src.canonical_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-0.5 text-xs text-ink-400 hover:text-red-600 transition-colors ml-auto"
                          >
                            <span>Open on YouTube</span>
                            <ExternalLink className="h-3 w-3" />
                          </a>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {filteredSources.length === 0 && sources.length > 0 && (
          <div className="mt-4 rounded-xl border border-dashed border-ink-200 bg-white/50 px-6 py-8 text-center">
            <p className="text-sm text-ink-500">
              No materials in this category. Try a different filter.
            </p>
          </div>
        )}

        {sources.length === 0 && (
          <div className="mt-4 rounded-xl border border-dashed border-ink-200 bg-white/50 px-6 py-8 text-center">
            <p className="text-sm text-ink-500">
              No course materials uploaded yet. Upload a PDF, PPTX, MP4, or add a YouTube link to get started.
            </p>
          </div>
        )}
      </section>

      {/* Learning Tools */}
      <section className="mt-8">
        <h2 className="font-display text-lg font-semibold text-ink-900 mb-4">
          Learning Tools
        </h2>
        <div className="grid gap-4 sm:grid-cols-2">
          {/* AI Tutor */}
          <Link
            to={`/courses/${course.id}/tutor`}
            className="card-hover group block p-5"
          >
            <div className="flex items-start gap-3">
              <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-600 text-white">
                <Sparkles className="h-5.5 w-5.5" />
              </span>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <h3 className="font-display text-base font-semibold text-ink-900 group-hover:text-brand-700 transition-colors">
                    AI Tutor
                  </h3>
                  <span className="badge-success">
                    <CheckCircle className="h-3 w-3" />
                    Available
                  </span>
                </div>
                <p className="mt-1.5 text-sm text-ink-500">
                  Ask questions grounded in your course material with page, slide, and YouTube timestamp citations.
                </p>
              </div>
            </div>
          </Link>

          {/* Assessments */}
          <Link
            to={`/courses/${course.id}/assessments`}
            className="card-hover group block p-5"
          >
            <div className="flex items-start gap-3">
              <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-600 text-white">
                <BarChart3 className="h-5.5 w-5.5" />
              </span>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <h3 className="font-display text-base font-semibold text-ink-900 group-hover:text-brand-700 transition-colors">
                    Assessments
                  </h3>
                  <span className="badge-success">
                    <CheckCircle className="h-3 w-3" />
                    Available
                  </span>
                </div>
                <p className="mt-1.5 text-sm text-ink-500">
                  Generate AI-powered quizzes from your course material with grounded feedback.
                </p>
              </div>
            </div>
          </Link>

          {/* My Learning */}
          <Link
            to={`/courses/${course.id}/learning`}
            className="card-hover group block p-5"
          >
            <div className="flex items-start gap-3">
              <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-600 text-white">
                <TrendingUp className="h-5.5 w-5.5" />
              </span>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <h3 className="font-display text-base font-semibold text-ink-900 group-hover:text-brand-700 transition-colors">
                    My Learning
                  </h3>
                  <span className="badge-success">
                    <CheckCircle className="h-3 w-3" />
                    Available
                  </span>
                </div>
                <p className="mt-1.5 text-sm text-ink-500">
                  Track your mastery across topics and get personalized study recommendations.
                </p>
              </div>
            </div>
          </Link>
        </div>
      </section>

      {error && (
        <div className="mt-6 flex items-start gap-2.5 rounded-lg border border-err-200 bg-err-50 px-4 py-3">
          <AlertCircle className="h-5 w-5 text-err-500 shrink-0 mt-0.5" />
          <p className="text-sm text-err-700">{error}</p>
        </div>
      )}
    </AppLayout>
  );
}

function FilterButton({
  label,
  icon,
  count,
  active,
  onClick,
}: {
  label: string;
  icon?: React.ReactNode;
  count: number;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${
        active
          ? 'bg-brand-600 text-white'
          : 'bg-white text-ink-500 border border-ink-200 hover:border-ink-300'
      }`}
    >
      {icon}
      {label}
      <span className={`text-[10px] ${active ? 'text-white/70' : 'text-ink-400'}`}>
        {count}
      </span>
    </button>
  );
}
