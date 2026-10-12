import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
} from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Sparkles,
  Send,
  BookOpen,
  FileText,
  Search,
  FileQuestion,
  Loader2,
  AlertCircle,
  Wifi,
  WifiOff,
} from 'lucide-react';
import { api, getErrorMessage, sendTutorMessageWithTimeout } from '@/lib/api';
import { TypingIndicator } from '@/components/TypingIndicator';
import { SourceCard } from '@/components/SourceCard';
import type { TutorResponse, TutorSource } from '@/types';

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
  const navigate = useNavigate();
  const [courseTitle, setCourseTitle] = useState('');
  const [courseLoading, setCourseLoading] = useState(true);
  const [courseError, setCourseError] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [chatError, setChatError] = useState('');
  const [connected, setConnected] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const cancelRef = useRef<(() => void) | null>(null);

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

  // Reset chat when course changes
  useEffect(() => {
    setMessages([]);
    setChatError('');
    setInput('');
  }, [courseId]);

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
        setConnected(false);
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
    <div className="flex h-screen flex-col bg-ink-50">
      {/* Header */}
      <header className="sticky top-0 z-20 border-b border-ink-200 bg-white/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-4 py-3 sm:px-6">
          <div className="flex items-center gap-3 min-w-0">
            <Link
              to={`/courses/${courseId}`}
              className="rounded-lg p-2 text-ink-500 hover:bg-ink-100 hover:text-ink-700 transition-colors shrink-0"
              aria-label="Back to course"
            >
              <ArrowLeft className="h-5 w-5" />
            </Link>
            <div className="flex items-center gap-2.5 min-w-0">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-600 text-white">
                <Sparkles className="h-4.5 w-4.5" />
              </span>
              <div className="min-w-0">
                <h1 className="font-display text-sm font-semibold text-ink-900 truncate">
                  AI Tutor
                </h1>
                <p className="text-xs text-ink-500 truncate">
                  {courseTitle || 'Course'}
                </p>
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
              <h2 className="font-display text-xl font-semibold text-ink-900 text-center">
                Ask anything about your course material.
              </h2>
              <p className="mt-2 text-sm text-ink-500 text-center max-w-md">
                Your AI tutor reads your uploaded PDFs, slides, and videos, then answers with citations from your actual content.
              </p>

              <div className="mt-8 w-full max-w-2xl">
                <p className="text-xs font-medium text-ink-400 mb-3 text-center">
                  Suggested questions
                </p>
                <div className="grid gap-3 sm:grid-cols-2">
                  {SUGGESTED_QUESTIONS.map((q) => (
                    <button
                      key={q}
                      onClick={() => handleSuggestion(q)}
                      disabled={sending}
                      className="card-hover flex items-center gap-3 p-3.5 text-left text-sm text-ink-700 hover:text-brand-700 transition-all"
                    >
                      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-ink-100 text-ink-400">
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

              {/* Typing indicator */}
              {sending && (
                <div className="flex items-start gap-3 animate-fade-in">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-600 text-white">
                    <Sparkles className="h-4 w-4" />
                  </span>
                  <div className="rounded-xl rounded-tl-sm bg-white border border-ink-200 px-4 py-3 shadow-card">
                    <TypingIndicator />
                  </div>
                </div>
              )}
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Composer */}
      <div className="sticky bottom-0 z-20 border-t border-ink-200 bg-white/90 backdrop-blur-md">
        <div className="mx-auto max-w-4xl px-4 py-3 sm:px-6 sm:py-4">
          {chatError && !sending && (
            <div className="mb-2.5 flex items-center gap-2 rounded-lg border border-err-200 bg-err-50 px-3 py-2">
              <AlertCircle className="h-4 w-4 text-err-500 shrink-0" />
              <p className="text-xs text-err-600 flex-1">{chatError}</p>
              <button
                onClick={() => setChatError('')}
                className="text-xs text-err-500 hover:text-err-700 font-medium"
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
                className="w-full resize-none rounded-xl border border-ink-200 bg-ink-50 px-4 py-3 text-sm text-ink-900 placeholder-ink-400 transition-colors focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-100 disabled:opacity-60"
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
          <p className="mt-1.5 text-center text-xs text-ink-400">
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
          <div className="rounded-xl rounded-tr-sm bg-brand-600 px-4 py-2.5 text-sm leading-relaxed text-white">
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
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-600 text-white">
        <Sparkles className="h-4 w-4" />
      </span>
      <div className="max-w-[85%] sm:max-w-[75%]">
        <div
          className={`rounded-xl rounded-tl-sm border px-4 py-3 text-sm leading-relaxed ${
            message.error
              ? 'border-err-200 bg-err-50 text-err-700'
              : message.grounded === false && !isConversational
                ? 'border-warn-200 bg-warn-50/40 text-ink-700'
                : 'border-ink-200 bg-white text-ink-800'
          }`}
        >
          {message.grounded === false && !message.error && !isConversational && (
            <div className="mb-2 flex items-center gap-1.5 text-xs font-medium text-warn-600">
              <Search className="h-3.5 w-3.5" />
              Not found in your material
            </div>
          )}
          <p className="whitespace-pre-wrap">{message.content}</p>
        </div>

        {/* Citations */}
        {message.sources && message.sources.length > 0 && (
          <div className="mt-3 space-y-2">
            <p className="text-xs font-medium text-ink-500 flex items-center gap-1.5">
              <FileText className="h-3.5 w-3.5" />
              Sources
            </p>
            {message.sources.map((src, i) => (
              <SourceCard key={`${src.source_id}-${i}`} source={src} index={i} />
            ))}
          </div>
        )}

        <p className="mt-1 text-xs text-ink-400">
          {formatTime(message.timestamp)}
        </p>
      </div>
    </div>
  );
}
