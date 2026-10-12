import React, { useState, useEffect } from 'react';
import { User, Mail, Loader2, CheckCircle2, AlertCircle, X } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { getErrorMessage } from '@/lib/api';

export interface EditProfileModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function EditProfileModal({ isOpen, onClose }: EditProfileModalProps) {
  const { user, updateProfile } = useAuth();
  const [displayName, setDisplayName] = useState('');
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (isOpen && user) {
      setDisplayName(user.display_name || '');
      setEmail(user.email || '');
      setError('');
      setSuccess('');
      setSaving(false);
    }
  }, [isOpen, user]);

  useEffect(() => {
    if (!isOpen) return;
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape' && !saving) {
        onClose();
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, saving, onClose]);

  if (!isOpen) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setSuccess('');

    const cleanName = displayName.trim();
    const cleanEmail = email.trim().toLowerCase();

    if (!cleanName) {
      setError('Display name is required.');
      return;
    }
    if (!cleanEmail) {
      setError('Email address is required.');
      return;
    }
    if (!cleanEmail.includes('@') || !cleanEmail.includes('.')) {
      setError('Please enter a valid email address.');
      return;
    }

    setSaving(true);
    try {
      await updateProfile({
        display_name: cleanName,
        email: cleanEmail,
      });
      setSuccess('Profile updated successfully!');
      setTimeout(() => {
        onClose();
      }, 700);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 animate-fade-in"
      onClick={() => !saving && onClose()}
      role="dialog"
      aria-modal="true"
      aria-labelledby="edit-profile-title"
    >
      <div className="absolute inset-0 bg-ink-900/40 dark:bg-black/60 backdrop-blur-sm" />
      <div
        className="relative w-full max-w-md rounded-2xl border border-ink-200 dark:border-ink-800 bg-white dark:bg-ink-900 shadow-pop animate-fade-in-up"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-ink-100 dark:border-ink-800 px-6 py-4">
          <div className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-50 text-brand-600 dark:bg-brand-950/60 dark:text-brand-400">
              <User className="h-5 w-5" />
            </span>
            <h3
              id="edit-profile-title"
              className="font-display text-base font-semibold text-ink-900 dark:text-ink-50"
            >
              Edit Profile
            </h3>
          </div>
          {!saving && (
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg p-1.5 text-ink-400 hover:bg-ink-100 hover:text-ink-600 dark:text-ink-500 dark:hover:bg-ink-800 dark:hover:text-ink-300 transition-colors"
              aria-label="Close"
            >
              <X className="h-4.5 w-4.5" />
            </button>
          )}
        </div>

        {/* Body */}
        <form onSubmit={handleSubmit} noValidate className="p-6 space-y-4">
          {error && (
            <div className="flex items-start gap-2.5 rounded-lg border border-err-200 dark:border-err-800 bg-err-50 dark:bg-err-950/40 p-3 text-xs text-err-700 dark:text-err-300">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5 text-err-600 dark:text-err-400" />
              <span>{error}</span>
            </div>
          )}

          {success && (
            <div className="flex items-center gap-2.5 rounded-lg border border-accent-200 dark:border-accent-800 bg-accent-50 dark:bg-accent-950/40 p-3 text-xs text-accent-700 dark:text-accent-300">
              <CheckCircle2 className="h-4 w-4 shrink-0 text-accent-600 dark:text-accent-400" />
              <span>{success}</span>
            </div>
          )}

          <div>
            <label htmlFor="profile-display-name" className="label">
              Display Name <span className="text-err-500">*</span>
            </label>
            <div className="relative">
              <User className="absolute left-3.5 top-3 h-4 w-4 text-ink-400 dark:text-ink-500" />
              <input
                id="profile-display-name"
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="Your full name"
                required
                disabled={saving}
                maxLength={255}
                className="input pl-10"
              />
            </div>
          </div>

          <div>
            <label htmlFor="profile-email" className="label">
              Email Address <span className="text-err-500">*</span>
            </label>
            <div className="relative">
              <Mail className="absolute left-3.5 top-3 h-4 w-4 text-ink-400 dark:text-ink-500" />
              <input
                id="profile-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@example.com"
                required
                disabled={saving}
                maxLength={255}
                className="input pl-10"
              />
            </div>
          </div>

          <div className="mt-6 flex items-center justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={saving}
              className="btn-secondary"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="btn-primary"
            >
              {saving ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Saving…
                </>
              ) : (
                'Save Changes'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
