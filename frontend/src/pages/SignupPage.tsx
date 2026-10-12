import { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { User as UserIcon, Mail, Lock, Eye, EyeOff, Loader2, AlertCircle, ArrowLeft } from 'lucide-react';
import { Logo } from '@/components/Logo';
import { ThemeToggle } from '@/components/ThemeToggle';
import { useAuth } from '@/contexts/AuthContext';
import { getErrorMessage } from '@/lib/api';

export function SignupPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { signup } = useAuth();

  const [displayName, setDisplayName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState<{
    displayName?: string;
    email?: string;
    password?: string;
    confirmPassword?: string;
  }>({});

  const from = (location.state as { from?: { pathname?: string } })?.from?.pathname || '/dashboard';

  function validate(): boolean {
    const errors: {
      displayName?: string;
      email?: string;
      password?: string;
      confirmPassword?: string;
    } = {};

    const trimmedName = displayName.trim();
    if (!trimmedName) {
      errors.displayName = 'Display name is required.';
    } else if (trimmedName.length < 2) {
      errors.displayName = 'Display name must be at least 2 characters.';
    }

    const trimmedEmail = email.trim();
    if (!trimmedEmail) {
      errors.email = 'Email is required.';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmedEmail)) {
      errors.email = 'Please enter a valid email address.';
    }

    if (!password) {
      errors.password = 'Password is required.';
    } else if (password.length < 6) {
      errors.password = 'Password must be at least 6 characters long.';
    }

    if (!confirmPassword) {
      errors.confirmPassword = 'Please confirm your password.';
    } else if (password !== confirmPassword) {
      errors.confirmPassword = 'Passwords do not match.';
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');

    if (!validate()) {
      return;
    }

    setSubmitting(true);

    try {
      await signup({
        email: email.trim(),
        password,
        display_name: displayName.trim(),
      });
      navigate(from, { replace: true });
    } catch (err) {
      setError(getErrorMessage(err));
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-ink-50 dark:bg-ink-950 flex flex-col justify-between transition-colors duration-150">
      {/* Top Header */}
      <header className="px-6 py-4 flex items-center justify-between max-w-6xl mx-auto w-full">
        <Logo size="lg" showTagline taglineClassName="hidden sm:block" />
        <div className="flex items-center gap-3">
          <ThemeToggle id="signup-theme-toggle" />
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 text-sm font-medium text-ink-500 hover:text-ink-900 dark:text-ink-400 dark:hover:text-ink-100 transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Home
          </Link>
        </div>
      </header>

      {/* Main Form Section */}
      <main className="flex-1 flex items-center justify-center px-4 py-10 sm:px-6 lg:px-8">
        <div className="w-full max-w-md animate-fade-in-up">
          <div className="card p-6 sm:p-8 shadow-pop border border-ink-200">
            <div className="text-center mb-6">
              <h1 className="font-display text-2xl font-bold tracking-tight text-ink-900 dark:text-ink-50">
                Create your account
              </h1>
              <p className="mt-2 text-sm text-ink-500 dark:text-ink-400">
                Join LearnMate to start personalized, course-grounded studying
              </p>
            </div>

            {error && (
              <div
                className="mb-6 flex items-start gap-2.5 rounded-lg border border-err-200 bg-err-50 px-4 py-3 animate-fade-in"
                role="alert"
              >
                <AlertCircle className="h-5 w-5 text-err-500 shrink-0 mt-0.5" />
                <p className="text-sm text-err-700">{error}</p>
              </div>
            )}

            <form onSubmit={handleSubmit} noValidate className="space-y-4">
              <div>
                <label htmlFor="signup-name" className="label">
                  Display name
                </label>
                <div className="relative">
                  <span className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none text-ink-400">
                    <UserIcon className="h-4.5 w-4.5" />
                  </span>
                  <input
                    id="signup-name"
                    type="text"
                    autoFocus
                    required
                    value={displayName}
                    onChange={(e) => {
                      setDisplayName(e.target.value);
                      if (fieldErrors.displayName) {
                        setFieldErrors((prev) => ({ ...prev, displayName: undefined }));
                      }
                      if (error) setError('');
                    }}
                    placeholder="e.g. Alex Johnson"
                    className={`input pl-10 ${
                      fieldErrors.displayName ? 'border-err-300 focus:ring-err-100 focus:border-err-500' : ''
                    }`}
                    disabled={submitting}
                    maxLength={100}
                  />
                </div>
                {fieldErrors.displayName && (
                  <p className="mt-1 text-xs text-err-600 animate-fade-in">{fieldErrors.displayName}</p>
                )}
              </div>

              <div>
                <label htmlFor="signup-email" className="label">
                  Email address
                </label>
                <div className="relative">
                  <span className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none text-ink-400">
                    <Mail className="h-4.5 w-4.5" />
                  </span>
                  <input
                    id="signup-email"
                    type="email"
                    autoComplete="email"
                    required
                    value={email}
                    onChange={(e) => {
                      setEmail(e.target.value);
                      if (fieldErrors.email) {
                        setFieldErrors((prev) => ({ ...prev, email: undefined }));
                      }
                      if (error) setError('');
                    }}
                    placeholder="name@example.com"
                    className={`input pl-10 ${
                      fieldErrors.email ? 'border-err-300 focus:ring-err-100 focus:border-err-500' : ''
                    }`}
                    disabled={submitting}
                  />
                </div>
                {fieldErrors.email && (
                  <p className="mt-1 text-xs text-err-600 animate-fade-in">{fieldErrors.email}</p>
                )}
              </div>

              <div>
                <label htmlFor="signup-password" className="label">
                  Password
                </label>
                <div className="relative">
                  <span className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none text-ink-400">
                    <Lock className="h-4.5 w-4.5" />
                  </span>
                  <input
                    id="signup-password"
                    type={showPassword ? 'text' : 'password'}
                    autoComplete="new-password"
                    required
                    value={password}
                    onChange={(e) => {
                      setPassword(e.target.value);
                      if (fieldErrors.password) {
                        setFieldErrors((prev) => ({ ...prev, password: undefined }));
                      }
                      if (error) setError('');
                    }}
                    placeholder="Minimum 6 characters"
                    className={`input pl-10 pr-10 ${
                      fieldErrors.password ? 'border-err-300 focus:ring-err-100 focus:border-err-500' : ''
                    }`}
                    disabled={submitting}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    className="absolute inset-y-0 right-0 flex items-center pr-3 text-ink-400 hover:text-ink-600 dark:hover:text-ink-200"
                    tabIndex={-1}
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                  >
                    {showPassword ? <EyeOff className="h-4.5 w-4.5" /> : <Eye className="h-4.5 w-4.5" />}
                  </button>
                </div>
                {fieldErrors.password && (
                  <p className="mt-1 text-xs text-err-600 animate-fade-in">{fieldErrors.password}</p>
                )}
              </div>

              <div>
                <label htmlFor="signup-confirm-password" className="label">
                  Confirm password
                </label>
                <div className="relative">
                  <span className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none text-ink-400">
                    <Lock className="h-4.5 w-4.5" />
                  </span>
                  <input
                    id="signup-confirm-password"
                    type={showConfirmPassword ? 'text' : 'password'}
                    autoComplete="new-password"
                    required
                    value={confirmPassword}
                    onChange={(e) => {
                      setConfirmPassword(e.target.value);
                      if (fieldErrors.confirmPassword) {
                        setFieldErrors((prev) => ({ ...prev, confirmPassword: undefined }));
                      }
                      if (error) setError('');
                    }}
                    placeholder="Re-enter your password"
                    className={`input pl-10 pr-10 ${
                      fieldErrors.confirmPassword ? 'border-err-300 focus:ring-err-100 focus:border-err-500' : ''
                    }`}
                    disabled={submitting}
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword((v) => !v)}
                    className="absolute inset-y-0 right-0 flex items-center pr-3 text-ink-400 hover:text-ink-600 dark:hover:text-ink-200"
                    tabIndex={-1}
                    aria-label={showConfirmPassword ? 'Hide password' : 'Show password'}
                  >
                    {showConfirmPassword ? <EyeOff className="h-4.5 w-4.5" /> : <Eye className="h-4.5 w-4.5" />}
                  </button>
                </div>
                {fieldErrors.confirmPassword && (
                  <p className="mt-1 text-xs text-err-600 animate-fade-in">{fieldErrors.confirmPassword}</p>
                )}
              </div>

              <div className="pt-2">
                <button
                  type="submit"
                  disabled={submitting}
                  className="btn-primary w-full py-2.5 text-base justify-center shadow-md hover:shadow-lg transition-all"
                >
                  {submitting ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Creating account…
                    </>
                  ) : (
                    'Create Account'
                  )}
                </button>
              </div>
            </form>

            <div className="mt-6 border-t border-ink-100 dark:border-ink-800 pt-5 text-center">
              <p className="text-sm text-ink-500 dark:text-ink-400">
                Already have an account?{' '}
                <Link
                  to="/login"
                  state={{ from: location.state?.from }}
                  className="font-medium text-brand-600 hover:text-brand-700 dark:text-brand-400 dark:hover:text-brand-300 transition-colors"
                >
                  Sign in
                </Link>
              </p>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="py-4 text-center text-xs text-ink-400 dark:text-ink-500">
        LearnMate · Your AI-powered learning companion
      </footer>
    </div>
  );
}
