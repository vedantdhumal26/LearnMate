import { Link } from 'react-router-dom';
import {
  Sparkles,
  FileText,
  BookMarked,
  GraduationCap,
  ArrowRight,
  Upload,
  Search,
  MessageSquare,
  Brain,
  Check,
} from 'lucide-react';
import { Logo } from '@/components/Logo';
import { ThemeToggle } from '@/components/ThemeToggle';
import { useAuth } from '@/contexts/AuthContext';

const features = [
  {
    icon: Brain,
    title: 'Course-grounded AI',
    description:
      'Your AI tutor reads your uploaded material and answers only from what it finds there — no hallucinations, no guesswork.',
  },
  {
    icon: FileText,
    title: 'Page-level citations',
    description:
      'Every answer includes direct citations to the exact page and excerpt from your source PDF, so you can verify instantly.',
  },
  {
    icon: BookMarked,
    title: 'Personalized learning',
    description:
      'Upload material for any course and get a tailored tutor session scoped to exactly what you need to study.',
  },
];

const steps = [
  { icon: Upload, label: 'Upload', description: 'Add your course PDF' },
  { icon: Search, label: 'Understand', description: 'AI reads and indexes' },
  { icon: MessageSquare, label: 'Ask', description: 'Question your material' },
  { icon: GraduationCap, label: 'Learn', description: 'Get grounded answers' },
];

export function LandingPage() {
  const { isAuthenticated } = useAuth();

  return (
    <div className="min-h-screen bg-ink-50 dark:bg-ink-950 text-ink-900 dark:text-ink-100 transition-colors duration-150">
      {/* Nav */}
      <header className="sticky top-0 z-30 border-b border-ink-200/60 bg-ink-50/80 backdrop-blur-md dark:border-ink-800 dark:bg-ink-950/80">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3.5 sm:px-6 lg:px-8">
          <Logo />
          <nav className="flex items-center gap-2 sm:gap-4">
            <ThemeToggle id="landing-theme-toggle" />
            {isAuthenticated ? (
              <>
                <Link to="/dashboard" className="btn-ghost text-sm">
                  Dashboard
                </Link>
                <Link to="/courses/new" className="btn-primary text-sm">
                  Create Course
                </Link>
              </>
            ) : (
              <>
                <Link to="/login" className="btn-ghost text-sm">
                  Sign In
                </Link>
                <Link to="/signup" className="btn-primary text-sm">
                  Get Started
                </Link>
              </>
            )}
          </nav>
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="mx-auto max-w-6xl px-4 pt-16 pb-20 sm:px-6 lg:px-8 lg:pt-24 lg:pb-28">
          <div className="grid items-center gap-12 lg:grid-cols-2">
            <div className="animate-fade-in-up">
              <span className="badge-brand mb-5">
                <Sparkles className="h-3.5 w-3.5" />
                AI-Powered Learning
              </span>
              <h1 className="font-display text-4xl font-bold leading-[1.1] tracking-tight text-ink-900 dark:text-ink-50 text-balance sm:text-5xl">
                Learn from your own course material.
              </h1>
              <p className="mt-5 max-w-md text-lg leading-relaxed text-ink-500 dark:text-ink-400">
                Upload your study material and get a grounded AI tutor that answers from your actual course content.
              </p>
              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <Link to="/courses/new" className="btn-primary text-base px-5 py-3">
                  Create a Course
                  <ArrowRight className="h-4.5 w-4.5" />
                </Link>
                <Link to="/dashboard" className="btn-secondary text-base px-5 py-3">
                  Explore Dashboard
                </Link>
              </div>
            </div>

            {/* Product preview mockup */}
            <div className="relative animate-fade-in" style={{ animationDelay: '0.15s' }}>
              <div className="rounded-2xl border border-ink-200 dark:border-ink-800 bg-white dark:bg-ink-900 shadow-pop overflow-hidden">
                {/* Window chrome */}
                <div className="flex items-center gap-2 border-b border-ink-100 dark:border-ink-800 bg-ink-50 dark:bg-ink-950 px-4 py-3">
                  <span className="h-2.5 w-2.5 rounded-full bg-err-300" />
                  <span className="h-2.5 w-2.5 rounded-full bg-warn-300" />
                  <span className="h-2.5 w-2.5 rounded-full bg-accent-300" />
                  <span className="ml-2 text-xs text-ink-400 dark:text-ink-500">LearnMate — Tutor</span>
                </div>
                {/* Chat preview */}
                <div className="space-y-4 p-5">
                  <div className="flex justify-end">
                    <div className="max-w-[75%] rounded-xl rounded-tr-sm bg-brand-600 px-4 py-2.5 text-sm text-white">
                      What is Newton's second law?
                    </div>
                  </div>
                  <div className="flex justify-start">
                    <div className="max-w-[80%] space-y-2">
                      <div className="rounded-xl rounded-tl-sm bg-ink-100 dark:bg-ink-800 px-4 py-2.5 text-sm text-ink-800 dark:text-ink-200">
                        Newton's second law states that the acceleration of an object is directly proportional to the net force acting on it and inversely proportional to its mass.
                      </div>
                      <div className="flex items-center gap-2 rounded-lg border border-ink-200 dark:border-ink-700 bg-ink-50 dark:bg-ink-800/60 px-3 py-2">
                        <FileText className="h-3.5 w-3.5 text-brand-600 dark:text-brand-400" />
                        <span className="text-xs font-medium text-ink-600 dark:text-ink-300">physics.pdf · Page 27</span>
                      </div>
                    </div>
                  </div>
                </div>
                {/* Composer */}
                <div className="border-t border-ink-100 dark:border-ink-800 p-3">
                  <div className="flex items-center gap-2 rounded-lg bg-ink-50 dark:bg-ink-800/80 px-3 py-2.5">
                    <span className="text-sm text-ink-400 dark:text-ink-500 flex-1">Ask something about your course…</span>
                    <span className="flex h-7 w-7 items-center justify-center rounded-md bg-brand-600 text-white">
                      <ArrowRight className="h-3.5 w-3.5" />
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="border-t border-ink-200/60 dark:border-ink-800 bg-white dark:bg-ink-900/60">
        <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6 lg:px-8 lg:py-20">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="font-display text-2xl font-bold tracking-tight text-ink-900 dark:text-ink-50 sm:text-3xl">
              Built for serious studying
            </h2>
            <p className="mt-3 text-ink-500 dark:text-ink-400">
              Everything you need to turn your course material into an interactive learning experience.
            </p>
          </div>
          <div className="mt-12 grid gap-6 md:grid-cols-3">
            {features.map((f) => (
              <div key={f.title} className="card-hover p-6">
                <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 dark:bg-brand-950/60 text-brand-600 dark:text-brand-400 mb-4">
                  <f.icon className="h-5.5 w-5.5" />
                </span>
                <h3 className="font-display text-base font-semibold text-ink-900 dark:text-ink-100">
                  {f.title}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-ink-500 dark:text-ink-400">
                  {f.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="border-t border-ink-200/60 dark:border-ink-800 bg-ink-50 dark:bg-ink-950">
        <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6 lg:px-8 lg:py-20">
          <h2 className="text-center font-display text-2xl font-bold tracking-tight text-ink-900 dark:text-ink-50 sm:text-3xl">
            How it works
          </h2>
          <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {steps.map((step, i) => (
              <div key={step.label} className="relative">
                <div className="card p-5 text-center">
                  <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-brand-600 text-white mb-3 shadow-sm">
                    <step.icon className="h-5.5 w-5.5" />
                  </span>
                  <p className="text-xs font-semibold text-brand-600 dark:text-brand-400 mb-1">
                    Step {i + 1}
                  </p>
                  <h3 className="font-display text-sm font-semibold text-ink-900 dark:text-ink-100">
                    {step.label}
                  </h3>
                  <p className="mt-1 text-xs text-ink-500 dark:text-ink-400">{step.description}</p>
                </div>
                {i < steps.length - 1 && (
                  <div className="hidden lg:block absolute top-1/2 -right-2.5 -translate-y-1/2 text-ink-300 dark:text-ink-700">
                    <ArrowRight className="h-4 w-4" />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="border-t border-ink-200/60 dark:border-ink-800 bg-white dark:bg-ink-900/60">
        <div className="mx-auto max-w-4xl px-4 py-16 text-center sm:px-6 lg:px-8 lg:py-20">
          <h2 className="font-display text-2xl font-bold tracking-tight text-ink-900 dark:text-ink-50 sm:text-3xl">
            Start learning from your material today
          </h2>
          <p className="mt-3 text-ink-500 dark:text-ink-400">
            Create a course, upload your PDF, and ask your AI tutor anything.
          </p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:justify-center">
            <Link to="/courses/new" className="btn-primary px-5 py-3 text-base">
              Create a Course
              <ArrowRight className="h-4.5 w-4.5" />
            </Link>
            <Link to="/dashboard" className="btn-secondary px-5 py-3 text-base">
              Explore Dashboard
            </Link>
          </div>
          <div className="mt-8 flex items-center justify-center gap-2 text-xs text-ink-400 dark:text-ink-500">
            <Check className="h-3.5 w-3.5 text-accent-500" />
            No setup required · Upload and start asking
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-ink-200/60 dark:border-ink-800 bg-ink-50 dark:bg-ink-950">
        <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <Logo showTagline />
            <p className="text-xs text-ink-400 dark:text-ink-500">
              Grounded, course-specific learning with verified citations.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
