import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  BookOpen,
  FileText,
  Presentation,
  Video,
  Sparkles,
  Loader2,
  AlertCircle,
  Calendar,
  Clock,
  CheckCircle,
  XCircle,
  BarChart3,
  TrendingUp,
  Play,
  ExternalLink,
  ShieldCheck,
  Link2,
  Edit3,
  Trash2,
} from 'lucide-react';
import { AppLayout } from '@/layouts/AppLayout';
import { UploadZone } from '@/components/UploadZone';
import { ErrorState } from '@/components/ErrorState';
import { RenameCourseModal } from '@/components/RenameCourseModal';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { api, getErrorMessage } from '@/lib/api';
import { getModality } from '@/components/CitationCard';
import type { Course, Source } from '@/types';

function formatDate(iso?: string | null): string {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleDateString('en-US', {
      month: 'long',
      day: 'numeric',
      year: 'numeric',
    });
  } catch {
    return String(iso);
  }
}

function formatTime(iso?: string | null): string {
  if (!iso) return 'Just now';
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return 'Just now';
    return d.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    });
  } catch {
    return 'Just now';
  }
}

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${String(secs).padStart(2, '0')}`;
}

type ProcessingStatus = 'pending' | 'processing' | 'completed' | 'failed' | string;

function StatusBadge({ status }: { status?: ProcessingStatus | null }) {
  const s = (status || 'pending').toLowerCase();
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
  return <span className="badge-neutral">{status || 'Ready'}</span>;
}

type FilterTab = 'all' | 'pdf' | 'pptx' | 'video' | 'youtube';

function getSourceModality(src: Source): FilterTab {
  if (src.modality === 'youtube' || src.video_id || (src.canonical_url && src.canonical_url.includes('youtube'))) {
    return 'youtube';
  }
  const name = (src.file_name || '').toLowerCase();
  if (name.includes('youtube') || name.startsWith('http')) {
    return 'youtube';
  }
  return getModality(src.file_name);
}

function SourceIcon({ src }: { src: Source }) {
  const modality = getSourceModality(src);
  if (modality === 'youtube') return <Play className="h-4 w-4 fill-current text-white" />;
  if (modality === 'pptx') return <Presentation className="h-5 w-5" />;
  if (modality === 'video') return <Video className="h-5 w-5" />;
  return <FileText className="h-5 w-5" />;
}

function SourceModalityBadge({ src }: { src: Source }) {
  const modality = getSourceModality(src);
  if (modality === 'youtube') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-red-50 dark:bg-red-950/50 px-2 py-0.5 text-[11px] font-semibold text-red-700 dark:text-red-400 border border-red-200 dark:border-red-800 shrink-0">
        <Play className="h-2.5 w-2.5 fill-current" />
        YouTube
      </span>
    );
  }
  const label = modality === 'pptx' ? 'Slides' : modality === 'video' ? 'Video' : 'PDF';
  return <span className="badge-neutral shrink-0">{label}</span>;
}

function sourceMatchesFilter(src: Source, filter: FilterTab): boolean {
  if (filter === 'all') return true;
  return getSourceModality(src) === filter;
}

export function CoursePage() {
  const { courseId } = useParams<{ courseId: string }>();
  const navigate = useNavigate();
  const [course, setCourse] = useState<Course | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState<FilterTab>('all');
  const [inputTab, setInputTab] = useState<'upload' | 'youtube'>('upload');
  const [youtubeUrl, setYoutubeUrl] = useState('');
  const [youtubeLoading, setYoutubeLoading] = useState(false);
  const [youtubeError, setYoutubeError] = useState('');
  const [youtubeSuccess, setYoutubeSuccess] = useState('');
  const [renameModalOpen, setRenameModalOpen] = useState(false);
  const [deleteCourseModalOpen, setDeleteCourseModalOpen] = useState(false);
  const [deleteCourseLoading, setDeleteCourseLoading] = useState(false);
  const [deleteCourseError, setDeleteCourseError] = useState('');
  const [materialToDelete, setMaterialToDelete] = useState<Source | null>(null);
  const [deleteMaterialLoading, setDeleteMaterialLoading] = useState(false);
  const [deleteMaterialError, setDeleteMaterialError] = useState('');
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(
    async (silent = false) => {
      if (!courseId) return;
      if (!silent) {
        setLoading(true);
      }
      setError('');
      try {
        const data = await api.getCourse(courseId);
        setCourse(data);
        setSources(data.sources ?? []);
      } catch (err) {
        setError(getErrorMessage(err));
      } finally {
        if (!silent) {
          setLoading(false);
        }
      }
    },
    [courseId],
  );

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
      await api.uploadFile(courseId, file);
      await load(true);
    },
    [courseId, load],
  );

  const handleAddYouTube = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!courseId || !youtubeUrl.trim()) return;
    setYoutubeLoading(true);
    setYoutubeError('');
    setYoutubeSuccess('');
    try {
      const res = await api.addYouTubeSource(courseId, youtubeUrl.trim());
      setYoutubeSuccess(res.message || 'YouTube source added successfully!');
      setYoutubeUrl('');
      await load();
    } catch (err) {
      setYoutubeError(getErrorMessage(err));
    } finally {
      setYoutubeLoading(false);
    }
  };

  function handleRenameSuccess(updated: Course) {
    setCourse((prev) =>
      prev
        ? {
            ...prev,
            title: updated.title,
            description: updated.description,
          }
        : null,
    );
  }

  async function handleConfirmDeleteCourse() {
    if (!courseId) return;
    setDeleteCourseLoading(true);
    setDeleteCourseError('');
    try {
      await api.deleteCourse(courseId);
      navigate('/dashboard', { replace: true });
    } catch (err) {
      setDeleteCourseError(getErrorMessage(err));
    } finally {
      setDeleteCourseLoading(false);
    }
  }

  async function handleConfirmDeleteMaterial() {
    if (!courseId || !materialToDelete) return;
    setDeleteMaterialLoading(true);
    setDeleteMaterialError('');
    try {
      await api.deleteCourseMaterial(courseId, materialToDelete.id);
      setSources((prev) => prev.filter((s) => s.id !== materialToDelete.id));
      setCourse((prev) =>
        prev
          ? {
              ...prev,
              source_count: Math.max(0, (prev.source_count ?? sources.length) - 1),
            }
          : null,
      );
      setMaterialToDelete(null);
    } catch (err) {
      setDeleteMaterialError(getErrorMessage(err));
    } finally {
      setDeleteMaterialLoading(false);
    }
  }

  if (loading) {
    return (
      <AppLayout>
        <div className="flex items-center gap-2 text-ink-500">
          <Loader2 className="h-5 w-5 animate-spin" />
          Loading course…
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
  const pdfCount = sources.filter((s) => getSourceModality(s) === 'pdf').length;
  const pptxCount = sources.filter((s) => getSourceModality(s) === 'pptx').length;
  const videoCount = sources.filter((s) => getSourceModality(s) === 'video').length;
  const youtubeCount = sources.filter((s) => getSourceModality(s) === 'youtube').length;

  return (
    <AppLayout>
      <Link
        to="/dashboard"
        className="inline-flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-700 dark:text-ink-400 dark:hover:text-ink-200 transition-colors mb-6"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Dashboard
      </Link>

      {/* Course Command Center Header */}
      <div className="card p-6">
        <div className="flex items-start gap-4">
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-brand-600 text-white shadow-sm">
            <BookOpen className="h-6 w-6" />
          </span>
          <div className="flex-1 min-w-0">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <h1 className="font-display text-2xl font-bold tracking-tight text-ink-900 dark:text-white">
                {course.title}
              </h1>
              <div className="flex items-center gap-2 shrink-0">
                <button
                  type="button"
                  id="course-rename-button"
                  onClick={() => setRenameModalOpen(true)}
                  className="btn-secondary text-xs px-3 py-1.5"
                  title="Rename Course"
                  aria-label="Rename Course"
                >
                  <Edit3 className="h-3.5 w-3.5" />
                  Rename
                </button>
                <button
                  type="button"
                  id="course-delete-button"
                  onClick={() => {
                    setDeleteCourseError('');
                    setDeleteCourseModalOpen(true);
                  }}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-err-200 dark:border-err-800 bg-white dark:bg-ink-900 px-3 py-1.5 text-xs font-medium text-err-600 dark:text-err-400 hover:bg-err-50 dark:hover:bg-err-950/40 transition-colors"
                  title="Delete Course"
                  aria-label="Delete Course"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  Delete Course
                </button>
              </div>
            </div>
            {course.description && (
              <p className="mt-2 text-sm leading-relaxed text-ink-500 dark:text-ink-400">
                {course.description}
              </p>
            )}
            <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-ink-500 dark:text-ink-400">
              <span className="inline-flex items-center gap-1.5">
                <Calendar className="h-3.5 w-3.5" />
                Created {formatDate(course.created_at)}
              </span>
              <span className="inline-flex items-center gap-1.5">
                <FileText className="h-3.5 w-3.5" />
                {sources.length} total source{sources.length !== 1 ? 's' : ''}
              </span>
              {(pdfCount > 0 || pptxCount > 0 || videoCount > 0 || youtubeCount > 0) && (
                <span className="inline-flex items-center gap-2 text-ink-400 dark:text-ink-500">
                  {pdfCount > 0 && <span>{pdfCount} PDF</span>}
                  {pptxCount > 0 && <span>· {pptxCount} Slides</span>}
                  {videoCount > 0 && <span>· {videoCount} MP4</span>}
                  {youtubeCount > 0 && <span>· {youtubeCount} YouTube</span>}
                </span>
              )}
            </div>

            {/* Quick action bar */}
            <div className="mt-4 flex flex-wrap items-center gap-2 pt-3 border-t border-ink-100 dark:border-ink-800">
              <span className="text-xs font-medium text-ink-400 dark:text-ink-500 mr-1">Direct Actions:</span>
              <Link
                to={`/courses/${course.id}/tutor`}
                className="inline-flex items-center gap-1.5 rounded-lg bg-brand-50 px-3 py-1.5 text-xs font-semibold text-brand-700 hover:bg-brand-100 dark:bg-brand-950/50 dark:text-brand-300 dark:hover:bg-brand-900/50 transition-colors"
              >
                <Sparkles className="h-3.5 w-3.5" />
                AI Tutor
              </Link>
              <Link
                to={`/courses/${course.id}/assessments`}
                className="inline-flex items-center gap-1.5 rounded-lg bg-brand-50 px-3 py-1.5 text-xs font-semibold text-brand-700 hover:bg-brand-100 dark:bg-brand-950/50 dark:text-brand-300 dark:hover:bg-brand-900/50 transition-colors"
              >
                <BarChart3 className="h-3.5 w-3.5" />
                Assessments
              </Link>
              <Link
                to={`/courses/${course.id}/learning`}
                className="inline-flex items-center gap-1.5 rounded-lg bg-brand-50 px-3 py-1.5 text-xs font-semibold text-brand-700 hover:bg-brand-100 dark:bg-brand-950/50 dark:text-brand-300 dark:hover:bg-brand-900/50 transition-colors"
              >
                <TrendingUp className="h-3.5 w-3.5" />
                My Learning
              </Link>
              <Link
                to="/evaluation"
                className="inline-flex items-center gap-1.5 rounded-lg bg-accent-50 px-3 py-1.5 text-xs font-semibold text-accent-700 hover:bg-accent-100 dark:bg-accent-950/50 dark:text-accent-300 dark:hover:bg-accent-900/50 transition-colors"
              >
                <ShieldCheck className="h-3.5 w-3.5" />
                Grounding Benchmark
              </Link>
            </div>
          </div>
        </div>
      </div>

      {/* Multimodal Course Materials Section */}
      <section className="mt-8">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
          <div>
            <h2 className="font-display text-lg font-semibold text-ink-900 dark:text-white">
              Course Materials
            </h2>
            <p className="text-xs text-ink-500 dark:text-ink-400 mt-0.5">
              Multimodal ingestion across PDFs, lecture slides, video files, and YouTube.
            </p>
          </div>

          {/* Mode Switcher Tabs */}
          <div className="flex items-center gap-1 rounded-xl bg-ink-100 dark:bg-ink-800 p-1 self-start sm:self-auto">
            <button
              type="button"
              onClick={() => setInputTab('upload')}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${
                inputTab === 'upload'
                  ? 'bg-white dark:bg-ink-900 text-ink-900 dark:text-white shadow-sm'
                  : 'text-ink-600 dark:text-ink-400 hover:text-ink-900 dark:hover:text-white'
              }`}
            >
              Upload Files (PDF / PPTX / MP4)
            </button>
            <button
              type="button"
              onClick={() => setInputTab('youtube')}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-all inline-flex items-center gap-1.5 ${
                inputTab === 'youtube'
                  ? 'bg-white dark:bg-ink-900 text-red-700 dark:text-red-400 shadow-sm font-semibold'
                  : 'text-ink-600 dark:text-ink-400 hover:text-ink-900 dark:hover:text-white'
              }`}
            >
              <Play className="h-3 w-3 fill-current text-red-600 dark:text-red-400" />
              Add YouTube Video
            </button>
          </div>
        </div>

        {/* Input Panel */}
        {inputTab === 'upload' ? (
          <UploadZone onUpload={handleUpload} />
        ) : (
          <div className="card p-5 border-dashed border-2 border-brand-200 dark:border-brand-800 bg-brand-50/20 dark:bg-brand-950/20">
            <div className="flex items-center gap-3 mb-3">
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-red-600 text-white shadow-sm">
                <Play className="h-4 w-4 fill-current" />
              </span>
              <div>
                <h3 className="text-sm font-semibold text-ink-900 dark:text-white">Ingest YouTube Video</h3>
                <p className="text-xs text-ink-500 dark:text-ink-400">
                  Provide a YouTube URL to extract transcript segments, timestamps, and index into grounded citations.
                </p>
              </div>
            </div>
            <form onSubmit={handleAddYouTube} className="space-y-3">
              <div className="flex flex-col sm:flex-row gap-2">
                <div className="relative flex-1">
                  <Link2 className="absolute left-3 top-2.5 h-4 w-4 text-ink-400 dark:text-ink-500" />
                  <input
                    type="url"
                    value={youtubeUrl}
                    onChange={(e) => setYoutubeUrl(e.target.value)}
                    placeholder="https://www.youtube.com/watch?v=... or https://youtu.be/..."
                    required
                    disabled={youtubeLoading}
                    className="w-full rounded-lg border border-ink-200 dark:border-ink-800 bg-white dark:bg-ink-900 pl-9 pr-3.5 py-2 text-sm text-ink-900 dark:text-white placeholder:text-ink-400 dark:placeholder:text-ink-500 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 disabled:opacity-50"
                  />
                </div>
                <button
                  type="submit"
                  disabled={youtubeLoading || !youtubeUrl.trim()}
                  className="btn-primary inline-flex items-center justify-center gap-2 px-5 py-2 text-sm whitespace-nowrap shrink-0 disabled:opacity-50"
                >
                  {youtubeLoading ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Ingesting Video…
                    </>
                  ) : (
                    <>
                      <Play className="h-3.5 w-3.5 fill-current" />
                      Ingest YouTube
                    </>
                  )}
                </button>
              </div>
              {youtubeError && (
                <div className="flex items-start gap-2 text-xs text-err-600 dark:text-err-400 bg-err-50 dark:bg-err-950/40 border border-err-200 dark:border-err-800 rounded-lg p-2.5">
                  <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                  <span>{youtubeError}</span>
                </div>
              )}
              {youtubeSuccess && (
                <div className="flex items-start gap-2 text-xs text-accent-700 dark:text-accent-400 bg-accent-50 dark:bg-accent-950/40 border border-accent-200 dark:border-accent-800 rounded-lg p-2.5">
                  <CheckCircle className="h-4 w-4 shrink-0 mt-0.5" />
                  <span>{youtubeSuccess}</span>
                </div>
              )}
            </form>
          </div>
        )}

        {/* Filter tabs */}
        {sources.length > 0 && (
          <div className="mt-5 flex flex-wrap items-center gap-2">
            <FilterButton label="All" count={sources.length} active={filter === 'all'} onClick={() => setFilter('all')} />
            <FilterButton label="PDF" icon={<FileText className="h-3.5 w-3.5" />} count={pdfCount} active={filter === 'pdf'} onClick={() => setFilter('pdf')} />
            <FilterButton label="Slides" icon={<Presentation className="h-3.5 w-3.5" />} count={pptxCount} active={filter === 'pptx'} onClick={() => setFilter('pptx')} />
            <FilterButton label="Video" icon={<Video className="h-3.5 w-3.5" />} count={videoCount} active={filter === 'video'} onClick={() => setFilter('video')} />
            <FilterButton label="YouTube" icon={<Play className="h-3 w-3 fill-current text-red-600 dark:text-red-400" />} count={youtubeCount} active={filter === 'youtube'} onClick={() => setFilter('youtube')} />
          </div>
        )}

        {/* Sources List */}
        {filteredSources.length > 0 && (
          <div className="mt-4 space-y-3">
            {filteredSources.map((src) => {
              const modality = getSourceModality(src);
              return (
                <div
                  key={src.id || (src as unknown as { source_id?: string }).source_id}
                  className="card p-4 animate-fade-in hover:border-ink-300 dark:hover:border-ink-700 transition-colors"
                >
                  <div className="flex items-start gap-3">
                    <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${
                      modality === 'youtube'
                        ? 'bg-red-600 text-white shadow-sm'
                        : modality === 'video'
                        ? 'bg-brand-50 text-brand-600 dark:bg-brand-950/60 dark:text-brand-400'
                        : modality === 'pptx'
                        ? 'bg-accent-50 text-accent-600 dark:bg-accent-950/60 dark:text-accent-400'
                        : 'bg-ink-100 text-ink-500 dark:bg-ink-800 dark:text-ink-400'
                    }`}>
                      <SourceIcon src={src} />
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-center gap-2 min-w-0">
                          {src.canonical_url ? (
                            <a
                              href={src.canonical_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-sm font-medium text-brand-700 dark:text-brand-400 hover:underline truncate inline-flex items-center gap-1.5"
                              title={src.file_name || src.canonical_url}
                            >
                              <span>{src.file_name || src.canonical_url}</span>
                              <ExternalLink className="h-3.5 w-3.5 shrink-0 text-ink-400 dark:text-ink-500" />
                            </a>
                          ) : (
                            <p className="text-sm font-medium text-ink-800 dark:text-ink-200 truncate" title={src.file_name}>
                              {src.file_name}
                            </p>
                          )}
                          <SourceModalityBadge src={src} />
                        </div>
                        <div className="flex items-center gap-1.5 shrink-0">
                          <StatusBadge status={src.processing_status} />
                          <button
                            type="button"
                            onClick={() => {
                              setDeleteMaterialError('');
                              setMaterialToDelete(src);
                            }}
                            className="rounded-lg p-1.5 text-ink-400 hover:bg-err-50 hover:text-err-600 dark:hover:bg-err-950/60 dark:hover:text-err-400 transition-colors"
                            title={`Delete ${src.file_name}`}
                            aria-label={`Delete material ${src.file_name}`}
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                      </div>
                      <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-500 dark:text-ink-400">
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
                        {modality === 'video' && src.duration != null && (
                          <span>{formatDuration(src.duration)} duration</span>
                        )}
                        {modality === 'video' && src.segment_count != null && (
                          <span>{src.segment_count} segment{src.segment_count !== 1 ? 's' : ''}</span>
                        )}
                        {modality === 'youtube' && src.duration != null && (
                          <span>{formatDuration(src.duration)} duration</span>
                        )}
                        {modality === 'youtube' && src.segment_count != null && (
                          <span>{src.segment_count} segment{src.segment_count !== 1 ? 's' : ''}</span>
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
          <div className="mt-4 rounded-xl border border-dashed border-ink-200 dark:border-ink-800 bg-white/50 dark:bg-ink-900/50 px-6 py-8 text-center">
            <p className="text-sm text-ink-500 dark:text-ink-400">
              No materials found in the &ldquo;{filter}&rdquo; category. Try selecting &ldquo;All&rdquo;.
            </p>
          </div>
        )}

        {sources.length === 0 && (
          <div className="mt-4 rounded-xl border border-dashed border-ink-200 dark:border-ink-800 bg-white/50 dark:bg-ink-900/50 px-6 py-8 text-center">
            <p className="text-sm text-ink-500 dark:text-ink-400">
              No course materials added yet. Upload a PDF, lecture slides, video, or add a YouTube link above to start learning!
            </p>
          </div>
        )}
      </section>

      {/* Learning Tools */}
      <section className="mt-8">
        <h2 className="font-display text-lg font-semibold text-ink-900 dark:text-white mb-4">
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
                  <h3 className="font-display text-base font-semibold text-ink-900 dark:text-white group-hover:text-brand-700 dark:group-hover:text-brand-400 transition-colors">
                    AI Tutor
                  </h3>
                  <span className="badge-success">
                    <CheckCircle className="h-3 w-3" />
                    Available
                  </span>
                </div>
                <p className="mt-1.5 text-sm text-ink-500 dark:text-ink-400">
                  Ask questions grounded in your course materials with page, slide, and timestamp citations.
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
                  <h3 className="font-display text-base font-semibold text-ink-900 dark:text-white group-hover:text-brand-700 dark:group-hover:text-brand-400 transition-colors">
                    Assessments
                  </h3>
                  <span className="badge-success">
                    <CheckCircle className="h-3 w-3" />
                    Available
                  </span>
                </div>
                <p className="mt-1.5 text-sm text-ink-500 dark:text-ink-400">
                  Generate adaptive AI-powered quizzes from your course material with grounded feedback.
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
                  <h3 className="font-display text-base font-semibold text-ink-900 dark:text-white group-hover:text-brand-700 dark:group-hover:text-brand-400 transition-colors">
                    My Learning
                  </h3>
                  <span className="badge-success">
                    <CheckCircle className="h-3 w-3" />
                    Available
                  </span>
                </div>
                <p className="mt-1.5 text-sm text-ink-500 dark:text-ink-400">
                  Track topic mastery, identify knowledge gaps, and receive personalized recommendations.
                </p>
              </div>
            </div>
          </Link>

          {/* Grounding Evaluation */}
          <Link
            to="/evaluation"
            className="card-hover group block p-5"
          >
            <div className="flex items-start gap-3">
              <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-accent-600 text-white">
                <ShieldCheck className="h-5.5 w-5.5" />
              </span>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <h3 className="font-display text-base font-semibold text-ink-900 dark:text-white group-hover:text-accent-700 dark:group-hover:text-accent-400 transition-colors">
                    Grounding Evaluation
                  </h3>
                  <span className="badge-success">
                    <CheckCircle className="h-3 w-3" />
                    Benchmark
                  </span>
                </div>
                <p className="mt-1.5 text-sm text-ink-500 dark:text-ink-400">
                  Inspect empirical metrics for Faithfulness, Context Recall, Citation Precision, and Isolation Safety.
                </p>
              </div>
            </div>
          </Link>
        </div>
      </section>

      {error && (
        <div className="mt-6 flex items-start gap-2.5 rounded-lg border border-err-200 dark:border-err-800 bg-err-50 dark:bg-err-950/40 px-4 py-3">
          <AlertCircle className="h-5 w-5 text-err-500 shrink-0 mt-0.5" />
          <p className="text-sm text-err-700 dark:text-err-300">{error}</p>
        </div>
      )}

      {/* Rename Course Modal */}
      <RenameCourseModal
        isOpen={renameModalOpen}
        onClose={() => setRenameModalOpen(false)}
        course={course}
        onSuccess={handleRenameSuccess}
      />

      {/* Delete Course Confirmation Dialog */}
      <ConfirmDialog
        isOpen={deleteCourseModalOpen}
        onClose={() => !deleteCourseLoading && setDeleteCourseModalOpen(false)}
        onConfirm={handleConfirmDeleteCourse}
        title="Delete Course"
        description={
          <div>
            Are you sure you want to delete{' '}
            <strong className="text-ink-900 dark:text-ink-100">{course.title}</strong>?
            <p className="mt-2 text-xs text-err-600 dark:text-err-400 font-medium">
              This will permanently delete the course, all associated learning materials, uploaded files, and indexed vector embeddings. This action cannot be undone.
            </p>
          </div>
        }
        confirmLabel="Delete Course"
        cancelLabel="Keep Course"
        isDanger={true}
        isLoading={deleteCourseLoading}
        error={deleteCourseError}
      />

      {/* Delete Material Confirmation Dialog */}
      <ConfirmDialog
        isOpen={!!materialToDelete}
        onClose={() => !deleteMaterialLoading && setMaterialToDelete(null)}
        onConfirm={handleConfirmDeleteMaterial}
        title="Delete Learning Material"
        description={
          <div>
            Are you sure you want to delete{' '}
            <strong className="text-ink-900 dark:text-ink-100">
              {materialToDelete?.file_name}
            </strong>
            ?
            <p className="mt-2 text-xs text-err-600 dark:text-err-400 font-medium">
              All indexed chunks, citations, and vector embeddings for this material will be permanently removed from this course.
            </p>
          </div>
        }
        confirmLabel="Delete Material"
        cancelLabel="Keep Material"
        isDanger={true}
        isLoading={deleteMaterialLoading}
        error={deleteMaterialError}
      />
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
          : 'bg-white dark:bg-ink-900 text-ink-500 dark:text-ink-400 border border-ink-200 dark:border-ink-800 hover:border-ink-300 dark:hover:border-ink-700'
      }`}
    >
      {icon}
      {label}
      <span className={`text-[10px] ${active ? 'text-white/70' : 'text-ink-400 dark:text-ink-500'}`}>
        {count}
      </span>
    </button>
  );
}
