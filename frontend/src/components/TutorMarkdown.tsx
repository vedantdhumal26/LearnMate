import React, { Component, type ReactNode } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';

interface TutorMarkdownProps {
  content: string;
  className?: string;
}

interface ErrorBoundaryProps {
  content: string;
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

class MarkdownErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error) {
    console.warn('TutorMarkdown fallback triggered:', error);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="text-sm leading-relaxed whitespace-pre-wrap text-ink-800 dark:text-ink-200">
          {this.props.content}
        </div>
      );
    }
    return this.props.children;
  }
}

/**
 * Preprocess math expressions from LLM outputs:
 * 1. Converts \[ ... \] block math to $$ ... $$
 * 2. Converts \( ... \) inline math to $ ... $
 */
export function preprocessMath(text: string): string {
  if (!text) return '';
  let res = text.replace(/\\\[([\s\S]*?)\\\]/g, (_match, math) => `$$\n${math.trim()}\n$$`);
  res = res.replace(/\\\(([\s\S]*?)\\\)/g, (_match, math) => `$${math.trim()}$`);
  return res;
}

function getNodeText(node: unknown): string {
  if (!node) return '';
  if (typeof node === 'string') return node;
  if (typeof node === 'number') return String(node);
  if (Array.isArray(node)) return node.map(getNodeText).join('');
  if (typeof node === 'object' && node !== null && 'props' in node) {
    const el = node as { props?: { children?: unknown } };
    if (el.props?.children) {
      return getNodeText(el.props.children);
    }
  }
  return '';
}

export function TutorMarkdown({ content, className = '' }: TutorMarkdownProps) {
  const processed = preprocessMath(content);

  return (
    <MarkdownErrorBoundary content={content}>
      <div className={`tutor-content text-sm leading-relaxed ${className}`}>
        <ReactMarkdown
          remarkPlugins={[remarkGfm, remarkMath]}
          rehypePlugins={[
            [
              rehypeKatex,
              {
                throwOnError: false,
                strict: false,
                errorColor: '#dc2626',
              },
            ],
          ]}
          components={{
            h1: ({ children }) => (
              <h1 className="font-display text-base font-bold text-ink-900 dark:text-ink-50 mt-4 mb-2 first:mt-0 tracking-tight">
                {children}
              </h1>
            ),
            h2: ({ children }) => (
              <h2 className="font-display text-sm font-bold text-ink-900 dark:text-ink-50 mt-3.5 mb-1.5 first:mt-0 tracking-tight">
                {children}
              </h2>
            ),
            h3: ({ children }) => (
              <h3 className="font-display text-xs font-semibold uppercase tracking-wider text-ink-700 dark:text-ink-300 mt-3 mb-1 first:mt-0">
                {children}
              </h3>
            ),
            h4: ({ children }) => (
              <h4 className="font-display text-xs font-semibold text-ink-600 dark:text-ink-400 mt-2 mb-1 first:mt-0">
                {children}
              </h4>
            ),
            p: ({ children }) => {
              const plain = getNodeText(children).trim();
              const isSourceLine = /^sources?:/i.test(plain);
              if (isSourceLine) {
                return (
                  <p className="my-2.5 flex items-start gap-1.5 rounded-md border border-ink-200 dark:border-ink-700 bg-ink-50/80 dark:bg-ink-800/80 px-2.5 py-1.5 text-xs font-medium text-ink-600 dark:text-ink-300">
                    <span className="font-semibold text-brand-700 dark:text-brand-400">{children}</span>
                  </p>
                );
              }
              return (
                <p className="text-sm leading-relaxed text-ink-800 dark:text-ink-200 my-2 first:mt-0 last:mb-0">
                  {children}
                </p>
              );
            },
            ul: ({ children }) => (
              <ul className="my-2 list-disc space-y-1 pl-5 text-sm text-ink-800 dark:text-ink-200 marker:text-ink-400 dark:marker:text-ink-500">
                {children}
              </ul>
            ),
            ol: ({ children }) => (
              <ol className="my-2 list-decimal space-y-1 pl-5 text-sm text-ink-800 dark:text-ink-200 marker:text-ink-400 dark:marker:text-ink-500">
                {children}
              </ol>
            ),
            li: ({ children }) => (
              <li className="leading-relaxed pl-0.5 text-ink-800 dark:text-ink-200">
                {children}
              </li>
            ),
            strong: ({ children }) => (
              <strong className="font-semibold text-ink-900 dark:text-white">
                {children}
              </strong>
            ),
            em: ({ children }) => (
              <em className="italic text-ink-800 dark:text-ink-200">
                {children}
              </em>
            ),
            blockquote: ({ children }) => (
              <blockquote className="my-2.5 rounded-r-lg border-l-2 border-brand-400 bg-brand-50/50 dark:bg-brand-950/40 py-1.5 pl-3.5 pr-3 text-xs italic text-ink-700 dark:text-ink-200">
                {children}
              </blockquote>
            ),
            pre: ({ children }) => (
              <div className="my-3 overflow-hidden rounded-lg border border-ink-700 dark:border-ink-800 bg-ink-900 dark:bg-ink-950 shadow-sm">
                <div className="overflow-x-auto p-3 text-xs font-mono text-ink-100">
                  {children}
                </div>
              </div>
            ),
            code: ({ className, children, ...props }) => {
              const domProps = { ...props } as Record<string, unknown>;
              delete domProps.node;
              const isBlock = Boolean(className) || (typeof children === 'string' && children.includes('\n'));
              if (isBlock) {
                return (
                  <code className={`${className ?? ''} font-mono`} {...domProps}>
                    {children}
                  </code>
                );
              }
              return (
                <code
                  className="rounded bg-ink-100 dark:bg-ink-800 px-1.5 py-0.5 font-mono text-xs font-medium text-brand-700 dark:text-brand-300 border border-ink-200/60 dark:border-ink-700"
                  {...domProps}
                >
                  {children}
                </code>
              );
            },
            a: ({ href, children }) => (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium text-brand-600 dark:text-brand-400 underline underline-offset-2 hover:text-brand-700 dark:hover:text-brand-300 transition-colors"
              >
                {children}
              </a>
            ),
            table: ({ children }) => (
              <div className="my-3 overflow-x-auto rounded-lg border border-ink-200 dark:border-ink-800 shadow-sm">
                <table className="min-w-full divide-y divide-ink-200 dark:divide-ink-800 text-xs text-ink-800 dark:text-ink-200">
                  {children}
                </table>
              </div>
            ),
            thead: ({ children }) => (
              <thead className="bg-ink-100/70 dark:bg-ink-800/80 text-ink-700 dark:text-ink-200 font-semibold">
                {children}
              </thead>
            ),
            tbody: ({ children }) => (
              <tbody className="divide-y divide-ink-100 dark:divide-ink-800 bg-white dark:bg-ink-900/60">
                {children}
              </tbody>
            ),
            tr: ({ children }) => (
              <tr className="transition-colors hover:bg-ink-50/50 dark:hover:bg-ink-800/40">
                {children}
              </tr>
            ),
            th: ({ children }) => (
              <th className="px-3 py-2 text-left font-semibold text-ink-900 dark:text-ink-100">
                {children}
              </th>
            ),
            td: ({ children }) => (
              <td className="px-3 py-2 text-ink-700 dark:text-ink-300">
                {children}
              </td>
            ),
            hr: () => <hr className="my-3 border-ink-200 dark:border-ink-800" />,
          }}
        >
          {processed}
        </ReactMarkdown>
      </div>
    </MarkdownErrorBoundary>
  );
}
