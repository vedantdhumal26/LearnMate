import { Navigate, useLocation, Outlet } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { Logo } from '@/components/Logo';
import { Loader2 } from 'lucide-react';

export function ProtectedRoute({ children }: { children?: React.ReactNode }) {
  const { isAuthenticated, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-ink-50 p-4">
        <div className="flex flex-col items-center gap-4 animate-fade-in">
          <Logo />
          <div className="flex items-center gap-2.5 text-sm text-ink-500">
            <Loader2 className="h-4 w-4 animate-spin text-brand-600" />
            <span>Restoring your session…</span>
          </div>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return children ? <>{children}</> : <Outlet />;
}
