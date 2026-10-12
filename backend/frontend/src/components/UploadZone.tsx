import { useRef, useState, type DragEvent, type ChangeEvent } from 'react';
import { UploadCloud, FileText, Presentation, Video, X, Loader2, CheckCircle, AlertCircle, RefreshCw } from 'lucide-react';

type UploadPhase = 'idle' | 'uploading' | 'done' | 'failed';

interface UploadZoneProps {
  onUpload: (file: File) => Promise<void>;
  disabled?: boolean;
}

const MAX_SIZE = 100 * 1024 * 1024; // 100 MB
const ACCEPTED_EXTENSIONS = ['.pdf', '.pptx', '.mp4'];
const ACCEPTED_MIME = 'application/pdf,.pdf,application/vnd.openxmlformats-officedocument.presentationml.presentation,.pptx,video/mp4,.mp4';

function getFileExt(name: string): string {
  const lower = name.toLowerCase();
  const ext = lower.slice(lower.lastIndexOf('.'));
  return ext;
}

function isAccepted(file: File): boolean {
  const ext = getFileExt(file.name);
  return ACCEPTED_EXTENSIONS.includes(ext);
}

function getModalityIcon(name: string) {
  const ext = getFileExt(name);
  if (ext === '.pptx') return Presentation;
  if (ext === '.mp4') return Video;
  return FileText;
}

function getModalityLabel(name: string): string {
  const ext = getFileExt(name);
  if (ext === '.pptx') return 'Slides';
  if (ext === '.mp4') return 'Video';
  return 'PDF';
}

export function UploadZone({ onUpload, disabled }: UploadZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [phase, setPhase] = useState<UploadPhase>('idle');
  const [error, setError] = useState<string>('');

  function validate(file: File): string | null {
    if (!isAccepted(file)) {
      return 'Unsupported file type. Only PDF, PPTX, and MP4 files are supported.';
    }
    if (file.size > MAX_SIZE) {
      return 'File is too large. Maximum size is 100 MB.';
    }
    return null;
  }

  function handleFile(file: File) {
    const vErr = validate(file);
    if (vErr) {
      setError(vErr);
      setPhase('failed');
      setSelectedFile(file);
      return;
    }
    setError('');
    setSelectedFile(file);
    setPhase('uploading');
    onUpload(file).catch((err: unknown) => {
      setError(
        err instanceof Error ? err.message : 'Upload failed. Please try again.',
      );
      setPhase('failed');
    });
  }

  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(false);
    if (disabled) return;
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  }

  function onChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
    e.target.value = '';
  }

  function reset() {
    setSelectedFile(null);
    setPhase('idle');
    setError('');
  }

  const isProcessing = phase === 'uploading';

  return (
    <div className="space-y-3">
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED_MIME}
        className="hidden"
        onChange={onChange}
        disabled={disabled || isProcessing}
      />

      {phase === 'idle' && (
        <div
          role="button"
          tabIndex={0}
          onClick={() => !disabled && inputRef.current?.click()}
          onKeyDown={(e) => {
            if ((e.key === 'Enter' || e.key === ' ') && !disabled) {
              e.preventDefault();
              inputRef.current?.click();
            }
          }}
          onDragOver={(e) => {
            e.preventDefault();
            if (!disabled) setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          className={`flex flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-10 text-center transition-all duration-200 cursor-pointer ${
            dragOver
              ? 'border-brand-400 bg-brand-50/60 scale-[1.01]'
              : 'border-ink-300 bg-ink-50/40 hover:border-brand-300 hover:bg-brand-50/30'
          } ${disabled ? 'opacity-50 pointer-events-none' : ''}`}
        >
          <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-white text-brand-600 border border-ink-200 shadow-sm mb-3">
            <UploadCloud className="h-6 w-6" />
          </span>
          <p className="text-sm font-medium text-ink-700">
            Drop a file here, or click to browse
          </p>
          <div className="mt-3 flex flex-wrap items-center justify-center gap-3 text-xs text-ink-400">
            <span className="inline-flex items-center gap-1.5">
              <FileText className="h-4 w-4" />
              PDF
            </span>
            <span className="inline-flex items-center gap-1.5">
              <Presentation className="h-4 w-4" />
              PPTX
            </span>
            <span className="inline-flex items-center gap-1.5">
              <Video className="h-4 w-4" />
              MP4
            </span>
          </div>
          <p className="mt-2 text-xs text-ink-400">Up to 100 MB</p>
        </div>
      )}

      {phase !== 'idle' && selectedFile && (
        <div className="rounded-xl border border-ink-200 bg-white p-4 animate-fade-in">
          <div className="flex items-start gap-3">
            {(() => {
              const Icon = getModalityIcon(selectedFile.name);
              return (
                <span
                  className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${
                    phase === 'done'
                      ? 'bg-accent-50 text-accent-600'
                      : phase === 'failed'
                        ? 'bg-err-50 text-err-500'
                        : 'bg-brand-50 text-brand-600'
                  }`}
                >
                  {phase === 'done' ? (
                    <CheckCircle className="h-5 w-5" />
                  ) : phase === 'failed' ? (
                    <AlertCircle className="h-5 w-5" />
                  ) : isProcessing ? (
                    <Loader2 className="h-5 w-5 animate-spin" />
                  ) : (
                    <Icon className="h-5 w-5" />
                  )}
                </span>
              );
            })()}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <p className="text-sm font-medium text-ink-800 truncate">
                  {selectedFile.name}
                </p>
                <span className="badge-neutral shrink-0">
                  {getModalityLabel(selectedFile.name)}
                </span>
              </div>
              <p className="text-xs text-ink-500 mt-0.5">
                {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
              </p>
              {isProcessing && (
                <div className="mt-2.5">
                  <div className="flex items-center gap-2">
                    <div className="h-1 flex-1 overflow-hidden rounded-full bg-ink-100">
                      <div className="h-full w-1/3 rounded-full bg-brand-500 animate-pulse-soft" style={{ animation: 'shimmer 1.5s linear infinite', background: 'linear-gradient(90deg, transparent, #339eff, transparent)', backgroundSize: '200% 100%' }} />
                    </div>
                  </div>
                  <p className="mt-1.5 text-xs text-ink-500">
                    {getFileExt(selectedFile.name) === '.mp4'
                      ? 'Uploading and transcribing video…'
                      : getFileExt(selectedFile.name) === '.pptx'
                        ? 'Uploading and processing slides…'
                        : 'Uploading and processing…'}
                  </p>
                </div>
              )}
              {phase === 'done' && (
                <p className="mt-1.5 text-xs font-medium text-accent-600">
                  Material ready
                </p>
              )}
              {phase === 'failed' && (
                <p className="mt-1.5 text-xs font-medium text-err-600">
                  {error || 'Processing failed'}
                </p>
              )}
            </div>
            {!isProcessing && (
              <button
                onClick={reset}
                className="shrink-0 rounded-md p-1.5 text-ink-400 hover:bg-ink-100 hover:text-ink-600 transition-colors"
                aria-label="Dismiss"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
          {phase === 'failed' && (
            <button
              onClick={() => {
                reset();
                inputRef.current?.click();
              }}
              className="btn-secondary mt-3 w-full"
            >
              <RefreshCw className="h-4 w-4" />
              Retry upload
            </button>
          )}
        </div>
      )}
    </div>
  );
}
