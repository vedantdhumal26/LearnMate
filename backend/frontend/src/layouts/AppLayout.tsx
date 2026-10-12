import { type ReactNode } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { LayoutDashboard, BookOpen, Plus, Menu, X } from 'lucide-react';
import { useState } from 'react';
import { Logo } from '@/components/Logo';

const navItems = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/dashboard?tab=courses', label: 'Courses', icon: BookOpen },
];

export function AppLayout({ children }: { children: ReactNode }) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const location = useLocation();

  return (
    <div className="min-h-screen bg-ink-50">
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r border-ink-200 bg-white lg:flex">
        <div className="px-5 py-5 border-b border-ink-100">
          <Logo />
        </div>
        <nav className="flex-1 space-y-1 px-3 py-4">
          <NavLink
            to="/dashboard"
            end
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-brand-50 text-brand-700'
                  : 'text-ink-600 hover:bg-ink-100 hover:text-ink-900'
              }`
            }
          >
            <LayoutDashboard className="h-4.5 w-4.5" />
            Dashboard
          </NavLink>
          <NavLink
            to="/dashboard"
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                isActive && location.search.includes('tab=courses')
                  ? 'bg-brand-50 text-brand-700'
                  : 'text-ink-600 hover:bg-ink-100 hover:text-ink-900'
              }`
            }
          >
            <BookOpen className="h-4.5 w-4.5" />
            Courses
          </NavLink>
        </nav>
        <div className="px-3 pb-5">
          <NavLink to="/courses/new" className="btn-primary w-full">
            <Plus className="h-4 w-4" />
            Create Course
          </NavLink>
        </div>
      </aside>

      {/* Mobile top bar */}
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-ink-200 bg-white/90 px-4 py-3 backdrop-blur lg:hidden">
        <Logo />
        <button
          onClick={() => setMobileNavOpen((v) => !v)}
          className="rounded-lg p-2 text-ink-600 hover:bg-ink-100 transition-colors"
          aria-label="Toggle navigation"
          aria-expanded={mobileNavOpen}
        >
          {mobileNavOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </header>

      {/* Mobile nav drawer */}
      {mobileNavOpen && (
        <div className="fixed inset-0 z-40 lg:hidden" onClick={() => setMobileNavOpen(false)}>
          <div className="absolute inset-0 bg-ink-900/20 backdrop-blur-sm animate-fade-in" />
          <nav
            className="absolute left-0 top-0 bottom-0 w-64 bg-white shadow-pop animate-slide-in p-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-6">
              <Logo />
            </div>
            <div className="space-y-1">
              <NavLink
                to="/dashboard"
                end
                onClick={() => setMobileNavOpen(false)}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-brand-50 text-brand-700'
                      : 'text-ink-600 hover:bg-ink-100'
                  }`
                }
              >
                <LayoutDashboard className="h-4.5 w-4.5" />
                Dashboard
              </NavLink>
              <NavLink
                to="/courses/new"
                onClick={() => setMobileNavOpen(false)}
                className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-ink-600 hover:bg-ink-100"
              >
                <Plus className="h-4.5 w-4.5" />
                Create Course
              </NavLink>
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
    </div>
  );
}
