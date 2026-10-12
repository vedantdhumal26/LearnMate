import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { ArrowLeft, Plus, Loader2, AlertCircle, CheckCircle } from 'lucide-react';
import { AppLayout } from '@/layouts/AppLayout';
import { api, getErrorMessage } from '@/lib/api';

export function CreateCoursePage() {
  const navigate = useNavigate();
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const titleValid = title.trim().length >= 1;
  const canSubmit = titleValid && !submitting;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!titleValid || submitting) return;

    setSubmitting(true);
    setError('');

    try {
      const course = await api.createCourse({
        title: title.trim(),
        description: description.trim() || undefined,
      });
      setSuccess(true);
      setTimeout(() => {
        navigate(`/courses/${course.id}`);
      }, 600);
    } catch (err) {
      setError(getErrorMessage(err));
      setSubmitting(false);
    }
  }

  return (
    <AppLayout>
      <Link
        to="/dashboard"
        className="inline-flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-700 transition-colors mb-6"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Dashboard
      </Link>

      <div className="max-w-xl">
        <h1 className="font-display text-2xl font-bold tracking-tight text-ink-900">
          Create a new course
        </h1>
        <p className="mt-1.5 text-sm text-ink-500">
          Give your course a title and description. You'll upload study material next.
        </p>

        {success && (
          <div className="mt-6 flex items-center gap-2.5 rounded-lg border border-accent-200 bg-accent-50 px-4 py-3 animate-fade-in">
            <CheckCircle className="h-5 w-5 text-accent-600" />
            <p className="text-sm font-medium text-accent-700">
              Course created! Redirecting…
            </p>
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-6 space-y-5">
          <div>
            <label htmlFor="title" className="label">
              Course title <span className="text-err-500">*</span>
            </label>
            <input
              id="title"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Engineering Physics"
              className="input"
              disabled={submitting || success}
              autoFocus
              maxLength={200}
            />
          </div>

          <div>
            <label htmlFor="description" className="label">
              Course description <span className="text-ink-400 font-normal">(optional)</span>
            </label>
            <textarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g. Core engineering physics concepts."
              className="input min-h-[100px] resize-y"
              disabled={submitting || success}
              maxLength={1000}
            />
          </div>

          {error && (
            <div className="flex items-start gap-2.5 rounded-lg border border-err-200 bg-err-50 px-4 py-3 animate-fade-in">
              <AlertCircle className="h-5 w-5 text-err-500 shrink-0 mt-0.5" />
              <p className="text-sm text-err-700">{error}</p>
            </div>
          )}

          <div className="flex items-center gap-3 pt-2">
            <button
              type="submit"
              disabled={!canSubmit}
              className="btn-primary"
            >
              {submitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Creating…
                </>
              ) : (
                <>
                  <Plus className="h-4 w-4" />
                  Create Course
                </>
              )}
            </button>
            <Link to="/dashboard" className="btn-ghost">
              Cancel
            </Link>
          </div>
        </form>
      </div>
    </AppLayout>
  );
}
