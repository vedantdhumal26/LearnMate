import { useState } from 'react';
import { FileText, Presentation, Video, ChevronDown, ChevronUp, ExternalLink, Play } from 'lucide-react';
import type { TutorSource, AssessmentSource } from '@/types';

type CitationLike = TutorSource | AssessmentSource;

export function formatVideoTimestamp(seconds: number): string {
  const totalSeconds = Math.floor(seconds);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const secs = totalSeconds % 60;
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

export function getModality(
  fileName: string,
  explicitModality?: string | null,
): 'pdf' | 'pptx' | 'video' | 'youtube' {
  if (explicitModality === 'youtube') return 'youtube';
  const lower = (fileName || '').toLowerCase();
  if (lower.includes('youtube.com') || lower.includes('youtu.be') || lower.startsWith('youtube:')) {
    return 'youtube';
  }
  if (lower.endsWith('.pdf')) return 'pdf';
  if (lower.endsWith('.pptx') || lower.endsWith('.ppt')) return 'pptx';
  if (
    lower.endsWith('.mp4') ||
    lower.endsWith('.avi') ||
    lower.endsWith('.mkv') ||
    lower.endsWith('.mov') ||
    lower.endsWith('.webm')
  ) {
    return 'video';
  }
  return 'pdf';
}

function getModalityIcon(modality: 'pdf' | 'pptx' | 'video' | 'youtube') {
  if (modality === 'pptx') return Presentation;
  if (modality === 'youtube') return Play;
  if (modality === 'video') return Video;
  return FileText;
}

function getModalityLabel(modality: 'pdf' | 'pptx' | 'video' | 'youtube'): string {
  if (modality === 'pptx') return 'Slides';
  if (modality === 'youtube') return 'YouTube';
  if (modality === 'video') return 'Video';
  return 'PDF';
}

function getLocationText(
  source: CitationLike,
  modality: 'pdf' | 'pptx' | 'video' | 'youtube',
): string | null {
  if (modality === 'video' || modality === 'youtube') {
    if (source.start_seconds != null && source.end_seconds != null) {
      return `${formatVideoTimestamp(source.start_seconds)} – ${formatVideoTimestamp(source.end_seconds)}`;
    }
    if (source.start_seconds != null) {
      return formatVideoTimestamp(source.start_seconds);
    }
    return null;
  }

  if (modality === 'pptx') {
    if (source.slide != null) return `Slide ${source.slide}`;
    if (source.page != null) return `Page ${source.page}`;
    return null;
  }

  // PDF
  if (source.page != null) return `Page ${source.page}`;
  return null;
}

function getDeepLinkUrl(source: CitationLike): string | null {
  const startSec = source.start_seconds != null ? Math.floor(source.start_seconds) : 0;
  if (source.canonical_url) {
    const separator = source.canonical_url.includes('?') ? '&' : '?';
    return startSec > 0 ? `${source.canonical_url}${separator}t=${startSec}s` : source.canonical_url;
  }
  if (source.video_id) {
    return startSec > 0
      ? `https://www.youtube.com/watch?v=${source.video_id}&t=${startSec}s`
      : `https://www.youtube.com/watch?v=${source.video_id}`;
  }
  return null;
}

export function CitationCard({ source, index }: { source: CitationLike; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const modality = getModality(source.file_name, source.modality);
  const Icon = getModalityIcon(modality);
  const locationText = getLocationText(source, modality);
  const modalityLabel = getModalityLabel(modality);
  const deepLink = getDeepLinkUrl(source);

  return (
    <div
      className="rounded-lg border border-ink-200 dark:border-ink-800 bg-ink-50/60 dark:bg-ink-900/90 animate-fade-in shadow-card transition-all"
      style={{ animationDelay: `${index * 60}ms` }}
    >
      {/* Collapsed header — always visible */}
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-2 p-3 text-left transition-colors hover:bg-ink-100/60 dark:hover:bg-ink-800/60 rounded-lg"
      >
        <span
          className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-md border ${
            modality === 'youtube'
              ? 'bg-err-50 dark:bg-err-950/60 text-err-600 dark:text-err-400 border-err-200 dark:border-err-800'
              : modality === 'video'
                ? 'bg-brand-50 dark:bg-brand-950/60 text-brand-600 dark:text-brand-400 border-brand-200 dark:border-brand-800'
                : modality === 'pptx'
                  ? 'bg-accent-50 dark:bg-accent-950/60 text-accent-700 dark:text-accent-300 border-accent-200 dark:border-accent-800'
                  : 'bg-white dark:bg-ink-800 text-ink-700 dark:text-ink-200 border-ink-200 dark:border-ink-700'
          }`}
        >
          <Icon className="h-3.5 w-3.5" />
        </span>
        <div className="flex-1 min-w-0">
          <span className="text-xs sm:text-sm font-medium text-ink-800 dark:text-ink-100 truncate block">
            {source.file_name}
          </span>
          {locationText && (
            <span className="text-xs text-ink-500 dark:text-ink-400 flex items-center gap-1 mt-0.5">
              <span className="font-semibold text-ink-700 dark:text-ink-200">{locationText}</span>
              <span className="text-ink-300 dark:text-ink-600">·</span>
              <span className="text-[11px] font-medium text-ink-500 dark:text-ink-400 uppercase tracking-wide">
                {modalityLabel}
              </span>
            </span>
          )}
        </div>

        {deepLink && (
          <a
            href={deepLink}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            title="Open in YouTube"
            className="rounded p-1 text-ink-400 hover:text-brand-600 hover:bg-ink-100 dark:hover:text-brand-400 dark:hover:bg-ink-800 transition-colors shrink-0 mr-1"
          >
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
        )}

        {expanded ? (
          <ChevronUp className="h-4 w-4 shrink-0 text-ink-400" />
        ) : (
          <ChevronDown className="h-4 w-4 shrink-0 text-ink-400" />
        )}
      </button>

      {/* Expanded detail */}
      {expanded && (
        <div className="border-t border-ink-100 dark:border-ink-800 px-3.5 pb-3.5 pt-3 animate-fade-in">
          <div className="space-y-2">
            <div className="flex items-start gap-2">
              <span className="text-xs font-medium text-ink-400 dark:text-ink-500 shrink-0 w-16">Type</span>
              <span className="text-xs font-medium text-ink-700 dark:text-ink-200">{modalityLabel}</span>
            </div>
            {locationText && (
              <div className="flex items-start gap-2">
                <span className="text-xs font-medium text-ink-400 dark:text-ink-500 shrink-0 w-16">
                  {modality === 'video' || modality === 'youtube' ? 'Time' : modality === 'pptx' ? 'Slide' : 'Page'}
                </span>
                <span className="text-xs text-ink-700 dark:text-ink-200 font-mono font-medium">{locationText}</span>
              </div>
            )}
            {deepLink && (
              <div className="flex items-start gap-2">
                <span className="text-xs font-medium text-ink-400 dark:text-ink-500 shrink-0 w-16">Link</span>
                <a
                  href={deepLink}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-xs font-medium text-brand-600 dark:text-brand-400 hover:text-brand-700 dark:hover:text-brand-300 underline underline-offset-2"
                >
                  Open {modalityLabel} at {locationText || 'timestamp'}
                  <ExternalLink className="h-3 w-3" />
                </a>
              </div>
            )}
            {source.excerpt && (
              <div className="flex items-start gap-2 pt-1">
                <span className="text-xs font-medium text-ink-400 dark:text-ink-500 shrink-0 w-16">Excerpt</span>
                <blockquote className="text-xs italic leading-relaxed text-ink-700 dark:text-ink-200 border-l-2 border-brand-400 pl-2.5 flex-1 bg-white/70 dark:bg-ink-800/70 py-1 rounded-r">
                  "{source.excerpt}"
                </blockquote>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
