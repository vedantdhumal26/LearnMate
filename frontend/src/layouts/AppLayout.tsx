import { type ReactNode, useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { LayoutDashboard, BookOpen, Plus, Menu, X, BarChart3, LogOut, Edit3 } from 'lucide-react';
import { Logo } from '@/components/Logo';
import { ThemeToggle } from '@/components/ThemeToggle';
import { EditProfileModal } from '@/components/EditProfileModal';
import { useAuth } from '@/contexts/AuthContext';

export function AppLayout({ children }: { children: ReactNode }) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [profileModalOpen, setProfileModalOpen] = useState(false);
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  function handleLogout() {
    logout();
    navigate('/login', { replace: true });
  }

  const initials = user?.display_name
    ? user.display_name
        .trim()
        .split(/\s+/)
        .map((p) => p[0])
        .filter(Boolean)
        .slice(0, 2)
        .join('')
        .toUpperCase()
    : 'U';

  return (
    <div className="min-h-screen bg-ink-50 dark:bg-ink-950 transition-colors duration-150">
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r border-ink-200 bg-white lg:flex dark:border-ink-800 dark:bg-ink-900">
        <div className="flex items-center justify-between px-5 py-4 border-b border-ink-100 dark:border-ink-800">
          <Logo />
          <ThemeToggle id="desktop-theme-toggle" />
        </div>
        <nav className="flex-1 space-y-1 px-3 py-4">
          <NavLink
            to="/dashboard"
            end
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-brand-50 text-brand-700 dark:bg-brand-950/60 dark:text-brand-300'
                  : 'text-ink-600 hover:bg-ink-100 hover:text-ink-900 dark:text-ink-300 dark:hover:bg-ink-800 dark:hover:text-ink-100'
              }`
            }
          >
            <LayoutDashboard className="h-4.5 w-4.5" />
            Dashboard
          </NavLink>
          <NavLink
            to="/courses"
            end
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-brand-50 text-brand-700 dark:bg-brand-950/60 dark:text-brand-300'
                  : 'text-ink-600 hover:bg-ink-100 hover:text-ink-900 dark:text-ink-300 dark:hover:bg-ink-800 dark:hover:text-ink-100'
              }`
            }
          >
            <BookOpen className="h-4.5 w-4.5" />
            Courses
          </NavLink>
          <NavLink
            to="/evaluation"
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-brand-50 text-brand-700 dark:bg-brand-950/60 dark:text-brand-300'
                  : 'text-ink-600 hover:bg-ink-100 hover:text-ink-900 dark:text-ink-300 dark:hover:bg-ink-800 dark:hover:text-ink-100'
              }`
            }
          >
            <BarChart3 className="h-4.5 w-4.5" />
            Evaluation
          </NavLink>
        </nav>

        <div className="px-3 pb-4 space-y-3">
          <NavLink to="/courses/new" className="btn-primary w-full">
            <Plus className="h-4 w-4" />
            Create Course
          </NavLink>

          {/* User profile & Logout */}
          <div className="border-t border-ink-100 dark:border-ink-800 pt-3">
            <div className="flex items-center justify-between rounded-lg p-2 bg-ink-50/70 border border-ink-100 dark:bg-ink-800/60 dark:border-ink-700">
              <div className="flex items-center gap-2.5 min-w-0">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-600 text-xs font-semibold text-white">
                  {initials}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-medium text-ink-900 dark:text-ink-100">
                    {user?.display_name || 'Learner'}
                  </p>
                  <p className="truncate text-[11px] text-ink-400 dark:text-ink-500">
                    {user?.email || ''}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                <button
                  type="button"
                  id="desktop-edit-profile-button"
                  onClick={() => setProfileModalOpen(true)}
                  className="rounded-md p-1.5 text-ink-400 hover:bg-ink-200/60 hover:text-brand-600 dark:hover:bg-ink-700 dark:hover:text-brand-400 transition-colors"
                  title="Edit Profile"
                  aria-label="Edit Profile"
                >
                  <Edit3 className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  id="desktop-logout-button"
                  onClick={handleLogout}
                  className="rounded-md p-1.5 text-ink-400 hover:bg-ink-200/60 hover:text-err-600 dark:hover:bg-ink-700 dark:hover:text-err-400 transition-colors"
                  title="Log out"
                  aria-label="Log out"
                >
                  <LogOut className="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </aside>

      {/* Mobile top bar */}
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-ink-200 bg-white/90 px-4 py-3 backdrop-blur lg:hidden dark:border-ink-800 dark:bg-ink-900/90">
        <Logo size="sm" />
        <div className="flex items-center gap-1.5">
          <ThemeToggle id="mobile-header-theme-toggle" />
          <button
            onClick={() => setMobileNavOpen((v) => !v)}
            className="rounded-lg p-2 text-ink-600 hover:bg-ink-100 dark:text-ink-300 dark:hover:bg-ink-800 transition-colors"
            aria-label="Toggle navigation"
            aria-expanded={mobileNavOpen}
          >
            {mobileNavOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </header>

      {/* Mobile nav drawer */}
      {mobileNavOpen && (
        <div className="fixed inset-0 z-40 lg:hidden" onClick={() => setMobileNavOpen(false)}>
          <div className="absolute inset-0 bg-ink-900/40 backdrop-blur-sm animate-fade-in" />
          <nav
            className="absolute left-0 top-0 bottom-0 w-64 bg-white shadow-pop animate-slide-in p-4 flex flex-col justify-between dark:bg-ink-900 dark:border-r dark:border-ink-800"
            onClick={(e) => e.stopPropagation()}
          >
            <div>
              <div className="mb-6 flex items-center justify-between">
                <Logo />
                <ThemeToggle id="mobile-drawer-theme-toggle" />
              </div>
              <div className="space-y-1">
                <NavLink
                  to="/dashboard"
                  end
                  onClick={() => setMobileNavOpen(false)}
                  className={({ isActive }) =>
                    `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                      isActive
                        ? 'bg-brand-50 text-brand-700 dark:bg-brand-950/60 dark:text-brand-300'
                        : 'text-ink-600 hover:bg-ink-100 dark:text-ink-300 dark:hover:bg-ink-800 dark:hover:text-ink-100'
                    }`
                  }
                >
                  <LayoutDashboard className="h-4.5 w-4.5" />
                  Dashboard
                </NavLink>
                <NavLink
                  to="/courses"
                  end
                  onClick={() => setMobileNavOpen(false)}
                  className={({ isActive }) =>
                    `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                      isActive
                        ? 'bg-brand-50 text-brand-700 dark:bg-brand-950/60 dark:text-brand-300'
                        : 'text-ink-600 hover:bg-ink-100 dark:text-ink-300 dark:hover:bg-ink-800 dark:hover:text-ink-100'
                    }`
                  }
                >
                  <BookOpen className="h-4.5 w-4.5" />
                  Courses
                </NavLink>
                <NavLink
                  to="/evaluation"
                  onClick={() => setMobileNavOpen(false)}
                  className={({ isActive }) =>
                    `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                      isActive
                        ? 'bg-brand-50 text-brand-700 dark:bg-brand-950/60 dark:text-brand-300'
                        : 'text-ink-600 hover:bg-ink-100 dark:text-ink-300 dark:hover:bg-ink-800 dark:hover:text-ink-100'
                    }`
                  }
                >
                  <BarChart3 className="h-4.5 w-4.5" />
                  Evaluation
                </NavLink>
                <NavLink
                  to="/courses/new"
                  onClick={() => setMobileNavOpen(false)}
                  className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-ink-600 hover:bg-ink-100 dark:text-ink-300 dark:hover:bg-ink-800 dark:hover:text-ink-100"
                >
                  <Plus className="h-4.5 w-4.5" />
                  Create Course
                </NavLink>
              </div>
            </div>

            {/* Mobile user profile & Logout */}
            <div className="border-t border-ink-100 dark:border-ink-800 pt-4">
              <div className="flex items-center justify-between rounded-lg p-2.5 bg-ink-50 dark:bg-ink-800/60 border border-ink-100 dark:border-ink-700">
                <div className="flex items-center gap-2.5 min-w-0">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-600 text-xs font-semibold text-white">
                    {initials}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-medium text-ink-900 dark:text-ink-100">
                      {user?.display_name || 'Learner'}
                    </p>
                    <p className="truncate text-[11px] text-ink-400 dark:text-ink-500">
                      {user?.email || ''}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  <button
                    type="button"
                    id="mobile-edit-profile-button"
                    onClick={() => {
                      setMobileNavOpen(false);
                      setProfileModalOpen(true);
                    }}
                    className="rounded-md p-1.5 text-ink-400 hover:bg-ink-200/60 hover:text-brand-600 dark:hover:bg-ink-700 dark:hover:text-brand-400 transition-colors"
                    title="Edit Profile"
                    aria-label="Edit Profile"
                  >
                    <Edit3 className="h-4 w-4" />
                  </button>
                  <button
                    type="button"
                    id="mobile-logout-button"
                    onClick={handleLogout}
                    className="rounded-md p-1.5 text-ink-400 hover:bg-ink-200/60 hover:text-err-600 dark:hover:bg-ink-700 dark:hover:text-err-400 transition-colors"
                    title="Log out"
                    aria-label="Log out"
                  >
                    <LogOut className="h-4 w-4" />
                  </button>
                </div>
              </div>
            </div>
          </nav>
        </div>
      )}

      {/* Main content */}
      <main className="lg:pl-60">
        <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          {children}
        </div>
      </main>

      {/* Edit profile modal */}
      <EditProfileModal
        isOpen={profileModalOpen}
        onClose={() => setProfileModalOpen(false)}
      />
    </div>
  );
}
