import { useState } from 'react';
import { FileText, Presentation, Video, Youtube, ExternalLink, ChevronDown, ChevronUp } from 'lucide-react';
import type { TutorSource, AssessmentSource } from '@/types';

type CitationLike = TutorSource | AssessmentSource;

export function formatVideoTimestamp(seconds: number): string {
  const totalSeconds = Math.floor(seconds);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const secs = totalSeconds % 60;
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

export function getModality(fileName: string, explicitModality?: string | null): 'pdf' | 'pptx' | 'video' | 'youtube' {
  if (explicitModality === 'youtube') return 'youtube';
  const lower = (fileName || '').toLowerCase();
  if (lower.startsWith('youtube') || lower.includes('youtu.be') || lower.includes('youtube.com')) return 'youtube';
  if (lower.endsWith('.pdf')) return 'pdf';
  if (lower.endsWith('.pptx')) return 'pptx';
  if (lower.endsWith('.mp4')) return 'video';
  // Fallback heuristics
  if (lower.endsWith('.ppt')) return 'pptx';
  if (lower.endsWith('.avi') || lower.endsWith('.mkv') || lower.endsWith('.mov') || lower.endsWith('.webm')) return 'video';
  return 'pdf';
}

function getModalityIcon(modality: 'pdf' | 'pptx' | 'video' | 'youtube') {
  if (modality === 'youtube') return Youtube;
  if (modality === 'pptx') return Presentation;
  if (modality === 'video') return Video;
  return FileText;
}

function getModalityLabel(modality: 'pdf' | 'pptx' | 'video' | 'youtube'): string {
  if (modality === 'youtube') return 'YouTube';
  if (modality === 'pptx') return 'Slides';
  if (modality === 'video') return 'Video';
  return 'PDF';
}

function getLocationText(source: CitationLike, modality: 'pdf' | 'pptx' | 'video' | 'youtube'): string | null {
  if (modality === 'youtube' || modality === 'video') {
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

export function buildYouTubeDeepLink(source: CitationLike): string | null {
  const anySource = source as any;
  let base = anySource.canonical_url || (anySource.video_id ? `https://www.youtube.com/watch?v=${anySource.video_id}` : null);
  
  if (!base && source.file_name) {
    const idMatch = source.file_name.match(/([a-zA-Z0-9_-]{11})/);
    if (idMatch) {
      base = `https://www.youtube.com/watch?v=${idMatch[1]}`;
    }
  }

  if (!base) return null;

  if (source.start_seconds != null) {
    const startSec = Math.floor(source.start_seconds);
    const sep = base.includes('?') ? '&' : '?';
    return `${base}${sep}t=${startSec}s`;
  }
  return base;
}

export function CitationCard({ source, index }: { source: CitationLike; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const anySource = source as any;
  const modality = getModality(source.file_name, anySource.modality);
  const Icon = getModalityIcon(modality);
  const locationText = getLocationText(source, modality);
  const modalityLabel = getModalityLabel(modality);
  const youtubeUrl = modality === 'youtube' ? buildYouTubeDeepLink(source) : null;

  return (
    <div
      className="rounded-lg border border-ink-200 bg-ink-50/60 animate-fade-in"
      style={{ animationDelay: `${index * 60}ms` }}
    >
      {/* Collapsed header — always visible */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-2 p-3.5 text-left transition-colors hover:bg-ink-50"
      >
        <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-md border ${
          modality === 'youtube'
            ? 'bg-red-50 text-red-600 border-red-200'
            : modality === 'video'
            ? 'bg-brand-50 text-brand-600 border-brand-200'
            : modality === 'pptx'
            ? 'bg-amber-50 text-amber-600 border-amber-200'
            : 'bg-white text-brand-600 border-ink-200'
        }`}>
          <Icon className="h-3.5 w-3.5" />
        </span>
        <div className="flex-1 min-w-0">
          <span className="text-sm font-medium text-ink-800">
            {source.file_name}
          </span>
          {locationText && (
            <>
              <span className="text-ink-300 mx-1.5">•</span>
              <span className="text-xs text-ink-500">{locationText}</span>
            </>
          )}
        </div>
        {expanded ? (
          <ChevronUp className="h-4 w-4 shrink-0 text-ink-400" />
        ) : (
          <ChevronDown className="h-4 w-4 shrink-0 text-ink-400" />
        )}
      </button>

      {/* Expanded detail */}
      {expanded && (
        <div className="border-t border-ink-100 px-3.5 pb-3.5 pt-3 animate-fade-in">
          <div className="space-y-2">
            <div className="flex items-start gap-2">
              <span className="text-xs font-medium text-ink-400 shrink-0 w-16">Type</span>
              <span className={`text-xs font-medium ${modality === 'youtube' ? 'text-red-600' : 'text-ink-600'}`}>
                {modalityLabel}
              </span>
            </div>
            {locationText && (
              <div className="flex items-start gap-2">
                <span className="text-xs font-medium text-ink-400 shrink-0 w-16">
                  {modality === 'youtube' || modality === 'video' ? 'Time' : modality === 'pptx' ? 'Slide' : 'Page'}
                </span>
                <span className="text-xs text-ink-600">{locationText}</span>
              </div>
            )}
            {source.excerpt && (
              <div className="flex items-start gap-2">
                <span className="text-xs font-medium text-ink-400 shrink-0 w-16">Excerpt</span>
                <blockquote className="text-xs italic leading-relaxed text-ink-600 border-l-2 border-brand-300 pl-2.5 flex-1 whitespace-pre-line">
                  {source.excerpt}
                </blockquote>
              </div>
            )}

            {/* YouTube Deep Link Action */}
            {modality === 'youtube' && youtubeUrl && (
              <div className="pt-2 flex items-center">
                <a
                  href={youtubeUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-xs font-semibold text-red-600 hover:text-red-700 bg-red-50 hover:bg-red-100 px-3 py-1.5 rounded-md border border-red-200 transition-colors"
                  onClick={(e) => e.stopPropagation()}
                >
                  <Youtube className="h-4 w-4" />
                  <span>Open Video at {source.start_seconds != null ? formatVideoTimestamp(source.start_seconds) : 'Timestamp'}</span>
                  <ExternalLink className="h-3 w-3 ml-0.5" />
                </a>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
