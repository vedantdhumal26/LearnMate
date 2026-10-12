import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
} from 'react';
import { useParams, Link, useSearchParams } from 'react-router-dom';
import {
  ArrowLeft,
  Sparkles,
  Send,
  FileText,
  Search,
  FileQuestion,
  Loader2,
  AlertCircle,
  CheckCircle,
  Wifi,
  WifiOff,
} from 'lucide-react';
import { api, getErrorMessage, sendTutorMessageWithTimeout } from '@/lib/api';
import { TypingIndicator } from '@/components/TypingIndicator';
import { SourceCard } from '@/components/SourceCard';
import { TutorMarkdown } from '@/components/TutorMarkdown';
import { ThemeToggle } from '@/components/ThemeToggle';
import type { TutorResponse, TutorSource } from '@/types';

if (import.meta.env.DEV) {
  (window as unknown as { __TutorMarkdown?: typeof TutorMarkdown }).__TutorMarkdown = TutorMarkdown;
}

interface ChatMessage {
  id: string;
  role: 'user' | 'tutor';
  content: string;
  grounded?: boolean;
  sources?: TutorSource[];
  error?: boolean;
  timestamp: number;
  response_type?: string;
}

const SUGGESTED_QUESTIONS = [
  'Explain the main concepts in this chapter',
  'What is Newton\u2019s second law?',
  'Summarize the important points',
  'Explain this topic simply',
];

function formatTime(ts: number): string {
  return new Date(ts).toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
  });
}

let msgIdCounter = 0;
function nextMsgId(): string {
  msgIdCounter += 1;
  return `msg-${msgIdCounter}`;
}

export function TutorPage() {
  const { courseId } = useParams<{ courseId: string }>();
  const [searchParams] = useSearchParams();
  const prefilledTopic = searchParams.get('topic');
  const [courseTitle, setCourseTitle] = useState('');
  const [courseLoading, setCourseLoading] = useState(true);
  const [courseError, setCourseError] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [loadingPhase, setLoadingPhase] = useState<'searching' | 'generating'>('searching');
  const [chatError, setChatError] = useState('');
  const [connected, setConnected] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const cancelRef = useRef<(() => void) | null>(null);

  // Prefill prompt if navigating from study plan or recommendation
  useEffect(() => {
    if (prefilledTopic) {
      setInput(`Can you explain ${prefilledTopic} and summarize the key concepts from the course materials?`);
    }
  }, [prefilledTopic]);

  // Progressive loading phase
  useEffect(() => {
    if (sending) {
      setLoadingPhase('searching');
      const timer = setTimeout(() => {
        setLoadingPhase('generating');
      }, 2200);
      return () => clearTimeout(timer);
    } else {
      setLoadingPhase('searching');
    }
  }, [sending]);

  // Load course info
  useEffect(() => {
    if (!courseId) return;
    setCourseLoading(true);
    setCourseError('');
    api
      .getCourse(courseId)
      .then((c) => {
        setCourseTitle(c.title);
        setCourseLoading(false);
      })
      .catch((err) => {
        setCourseError(getErrorMessage(err));
        setCourseLoading(false);
      });
  }, [courseId]);

  // Reset chat when course changes, or initialize with prefilled topic
  useEffect(() => {
    setMessages([]);
    setChatError('');
    if (prefilledTopic) {
      setInput(`Can you explain ${prefilledTopic} and summarize the key concepts from the course materials?`);
    } else {
      setInput('');
    }
  }, [courseId, prefilledTopic]);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, sending]);

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [input]);

  const handleSend = useCallback(
    async (text: string) => {
      if (!courseId || !text.trim() || sending) return;

      const userMessage: ChatMessage = {
        id: nextMsgId(),
        role: 'user',
        content: text.trim(),
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, userMessage]);
      setInput('');
      setSending(true);
      setChatError('');
      setConnected(true);

      const { promise, cancel } = sendTutorMessageWithTimeout(
        courseId,
        text.trim(),
      );
      cancelRef.current = cancel;

      try {
        const response: TutorResponse = await promise;
        const tutorMessage: ChatMessage = {
          id: nextMsgId(),
          role: 'tutor',
          content: response.answer,
          grounded: response.grounded,
          sources: response.sources ?? [],
          timestamp: Date.now(),
          response_type: response.response_type,
        };
        setMessages((prev) => [...prev, tutorMessage]);
      } catch (err) {
        const msg = getErrorMessage(err);
        setChatError(msg);
        if ((err as { status?: number })?.status === 0) {
          setConnected(false);
        }
        const errorMessage: ChatMessage = {
          id: nextMsgId(),
          role: 'tutor',
          content: msg,
          error: true,
          timestamp: Date.now(),
        };
        setMessages((prev) => [...prev, errorMessage]);
      } finally {
        setSending(false);
        cancelRef.current = null;
      }
    },
    [courseId, sending],
  );

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend(input);
    }
  }

  function handleSuggestion(q: string) {
    handleSend(q);
  }

  const hasMessages = messages.length > 0;
  const canSend = input.trim().length > 0 && !sending;

  if (courseLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-ink-50">
        <div className="flex items-center gap-2.5 text-ink-500">
          <Loader2 className="h-5 w-5 animate-spin" />
          Loading course…
        </div>
      </div>
    );
  }

  if (courseError) {
    return (
      <div className="flex h-screen flex-col items-center justify-center bg-ink-50 px-4">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-err-100 text-err-500 mb-4">
          <AlertCircle className="h-7 w-7" />
        </div>
        <p className="max-w-sm text-center text-sm text-err-700">{courseError}</p>
        <Link to="/dashboard" className="btn-secondary mt-5">
          <ArrowLeft className="h-4 w-4" />
          Back to Dashboard
        </Link>
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col bg-ink-50 dark:bg-ink-950 transition-colors duration-150">
      {/* Header with Breadcrumb Navigation */}
      <header className="sticky top-0 z-20 border-b border-ink-200 dark:border-ink-800 bg-white/90 dark:bg-ink-900/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-4 py-3 sm:px-6">
          <div className="flex items-center gap-3 min-w-0">
            <Link
              to={`/courses/${courseId}`}
              className="rounded-lg p-2 text-ink-500 hover:bg-ink-100 hover:text-ink-700 dark:text-ink-400 dark:hover:bg-ink-800 dark:hover:text-ink-200 transition-colors shrink-0"
              aria-label="Back to course"
            >
              <ArrowLeft className="h-5 w-5" />
            </Link>
            <div className="flex items-center gap-2.5 min-w-0">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-600 text-white shadow-sm">
                <Sparkles className="h-4.5 w-4.5" />
              </span>
              <div className="min-w-0">
                <div className="flex items-center gap-1.5 text-xs text-ink-400 dark:text-ink-500">
                  <Link to="/dashboard" className="hover:text-ink-700 dark:hover:text-ink-200 truncate">Dashboard</Link>
                  <span>/</span>
                  <Link to={`/courses/${courseId}`} className="hover:text-ink-700 dark:hover:text-ink-200 truncate max-w-[120px] sm:max-w-[200px]">
                    {courseTitle || 'Course'}
                  </Link>
                  <span>/</span>
                  <span className="text-ink-700 dark:text-ink-300 font-medium">AI Tutor</span>
                </div>
                <h1 className="font-display text-sm font-semibold text-ink-900 dark:text-ink-100 truncate">
                  AI Study Assistant — Grounded Q&amp;A
                </h1>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <span
              className={`badge ${connected ? 'badge-success' : 'badge-error'}`}
            >
              {connected ? (
                <>
                  <Wifi className="h-3 w-3" />
                  Connected
                </>
              ) : (
                <>
                  <WifiOff className="h-3 w-3" />
                  Disconnected
                </>
              )}
            </span>
            <ThemeToggle id="tutor-theme-toggle" />
          </div>
        </div>
      </header>

      {/* Chat area */}
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-4xl px-4 py-6 sm:px-6">
          {/* Empty state */}
          {!hasMessages && !sending && (
            <div className="flex flex-col items-center justify-center py-12 animate-fade-in">
              <span className="flex h-16 w-16 items-center justify-center rounded-2xl bg-brand-50 text-brand-600 mb-5">
                <Sparkles className="h-8 w-8" />
              </span>
              <h2 className="font-display text-xl font-semibold text-ink-900 dark:text-ink-100 text-center">
                Ask anything about your course materials.
              </h2>
              <p className="mt-2 text-sm text-ink-500 dark:text-ink-400 text-center max-w-md">
                Your AI tutor searches your uploaded PDFs, slides, videos, and YouTube lectures, returning verified answers with exact page, slide, and timestamp citations.
              </p>

              <div className="mt-8 w-full max-w-2xl">
                <p className="text-xs font-medium text-ink-400 dark:text-ink-500 mb-3 text-center">
                  Suggested questions
                </p>
                <div className="grid gap-3 sm:grid-cols-2">
                  {SUGGESTED_QUESTIONS.map((q) => (
                    <button
                      key={q}
                      onClick={() => handleSuggestion(q)}
                      disabled={sending}
                      className="card-hover flex items-center gap-3 p-3.5 text-left text-sm text-ink-700 hover:text-brand-700 dark:text-ink-300 dark:hover:text-brand-400 transition-all"
                    >
                      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-ink-100 text-ink-400 dark:bg-ink-800 dark:text-ink-400">
                        <FileQuestion className="h-4 w-4" />
                      </span>
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Messages */}
          {hasMessages && (
            <div className="space-y-6">
              {messages.map((msg) => (
                <MessageBubble key={msg.id} message={msg} />
              ))}

              {/* Progressive typing / searching indicator */}
              {sending && (
                <div className="flex items-start gap-3 animate-fade-in">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-600 text-white shadow-sm">
                    <Sparkles className="h-4 w-4" />
                  </span>
                  <div className="rounded-xl rounded-tl-sm bg-white dark:bg-ink-900 border border-ink-200 dark:border-ink-800 px-4 py-3 shadow-card">
                    <div className="flex items-center gap-2.5">
                      <TypingIndicator />
                      <span className="text-xs font-medium text-ink-600 dark:text-ink-300 animate-pulse">
                        {loadingPhase === 'searching'
                          ? 'Searching your course materials…'
                          : 'Generating a grounded answer…'}
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Composer */}
      <div className="sticky bottom-0 z-20 border-t border-ink-200 dark:border-ink-800 bg-white/90 dark:bg-ink-900/90 backdrop-blur-md">
        <div className="mx-auto max-w-4xl px-4 py-3 sm:px-6 sm:py-4">
          {chatError && !sending && (
            <div className={`mb-2.5 flex items-start gap-2.5 rounded-xl border p-3 ${
              chatError.toLowerCase().includes('rate-limited')
                ? 'border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-700/60 dark:bg-amber-950/40 dark:text-amber-200'
                : 'border-err-200 bg-err-50 text-err-700 dark:border-err-800 dark:bg-err-950/50 dark:text-err-300'
            }`}>
              <AlertCircle className={`h-4 w-4 shrink-0 mt-0.5 ${
                chatError.toLowerCase().includes('rate-limited') ? 'text-amber-600 dark:text-amber-400' : 'text-err-500 dark:text-err-400'
              }`} />
              <div className="flex-1 text-xs leading-relaxed">
                <p className="font-semibold">
                  {chatError.toLowerCase().includes('rate-limited') ? 'AI Service Notice' : 'Request Notice'}
                </p>
                <p className="mt-0.5">{chatError}</p>
              </div>
              <button
                onClick={() => setChatError('')}
                className="text-xs font-medium text-ink-500 hover:text-ink-800 dark:text-ink-400 dark:hover:text-ink-200 self-start"
              >
                Dismiss
              </button>
            </div>
          )}
          <div className="flex items-end gap-2.5">
            <div className="flex-1 relative">
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask something about your course…"
                disabled={sending}
                rows={1}
                className="w-full resize-none rounded-xl border border-ink-200 dark:border-ink-700 bg-ink-50 dark:bg-ink-800/80 px-4 py-3 text-sm text-ink-900 dark:text-ink-100 placeholder-ink-400 dark:placeholder-ink-500 transition-colors focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-100 dark:focus:ring-brand-900/40 disabled:opacity-60"
                style={{ maxHeight: '160px' }}
                aria-label="Message input"
              />
            </div>
            <button
              onClick={() => handleSend(input)}
              disabled={!canSend}
              className="btn-primary shrink-0 h-[46px] w-[46px] rounded-xl p-0"
              aria-label="Send message"
            >
              {sending ? (
                <Loader2 className="h-4.5 w-4.5 animate-spin" />
              ) : (
                <Send className="h-4.5 w-4.5" />
              )}
            </button>
          </div>
          <p className="mt-1.5 text-center text-xs text-ink-400 dark:text-ink-500">
            Enter to send · Shift + Enter for new line
          </p>
        </div>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user';
  const isConversational = message.response_type === 'small_talk' || message.response_type === 'conversational';

  if (isUser) {
    return (
      <div className="flex justify-end animate-fade-in-up">
        <div className="max-w-[80%] sm:max-w-[70%]">
          <div className="rounded-xl rounded-tr-sm bg-brand-600 px-4 py-2.5 text-sm leading-relaxed text-white shadow-sm">
            {message.content}
          </div>
          <p className="mt-1 text-right text-xs text-ink-400">
            {formatTime(message.timestamp)}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-3 animate-fade-in-up">
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-600 text-white shadow-sm">
        <Sparkles className="h-4 w-4" />
      </span>
      <div className="max-w-[85%] sm:max-w-[75%]">
        <div
          className={`rounded-xl rounded-tl-sm border px-4 py-3 text-sm leading-relaxed ${
            message.error
              ? 'border-err-200 dark:border-err-800 bg-err-50 dark:bg-err-950/60 text-err-700 dark:text-err-300'
              : message.grounded === false && !isConversational
                ? 'border-warn-200 dark:border-warn-800 bg-warn-50/40 dark:bg-warn-950/30 text-ink-700 dark:text-ink-300'
                : 'border-ink-200 dark:border-ink-800 bg-white dark:bg-ink-900 text-ink-800 dark:text-ink-100 shadow-sm'
          }`}
        >
          {message.grounded === true && !message.error && !isConversational && (
            <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-emerald-700 dark:text-emerald-400">
              <CheckCircle className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />
              Grounded in course material
            </div>
          )}
          {message.grounded === false && !message.error && !isConversational && (
            <div className="mb-2 flex items-center gap-1.5 text-xs font-medium text-warn-600 dark:text-warn-400">
              <Search className="h-3.5 w-3.5" />
              Not found in your material
            </div>
          )}
          {message.error ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : (
            <TutorMarkdown content={message.content} />
          )}
        </div>

        {/* Citations */}
        {message.sources && message.sources.length > 0 && (
          <div className="mt-3.5 pt-3 border-t border-ink-100 dark:border-ink-800 space-y-2">
            <p className="text-xs font-semibold text-ink-600 dark:text-ink-400 flex items-center gap-1.5 uppercase tracking-wide">
              <FileText className="h-3.5 w-3.5 text-brand-600 dark:text-brand-400" />
              Verified Citations ({message.sources.length})
            </p>
            {message.sources.map((src, i) => (
              <SourceCard key={`${src.source_id}-${i}`} source={src} index={i} />
            ))}
          </div>
        )}

        <p className="mt-1 text-xs text-ink-400 dark:text-ink-500">
          {formatTime(message.timestamp)}
        </p>
      </div>
    </div>
  );
}
