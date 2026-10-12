import { Link } from 'react-router-dom';
import { GraduationCap } from 'lucide-react';

export function Logo({ to = '/', className = '' }: { to?: string; className?: string }) {
  return (
    <Link to={to} className={`flex items-center gap-2.5 group ${className}`}>
      <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600 text-white shadow-sm transition-transform group-hover:scale-105">
        <GraduationCap className="h-5 w-5" strokeWidth={2.2} />
      </span>
      <span className="font-display text-lg font-bold tracking-tight text-ink-900">
        LearnSphere<span className="text-brand-600"> AI</span>
      </span>
    </Link>
  );
}
