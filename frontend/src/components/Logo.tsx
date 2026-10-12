import { Link } from 'react-router-dom';

export type LogoSize = 'sm' | 'md' | 'lg';

export interface LogoProps {
  to?: string;
  className?: string;
  imageClassName?: string;
  textClassName?: string;
  taglineClassName?: string;
  showTagline?: boolean;
  alt?: string;
  size?: LogoSize;
}

const SIZE_CONFIGS: Record<
  LogoSize,
  {
    icon: string;
    text: string;
    gap: string;
    tagline: string;
  }
> = {
  // Mobile header: icon 32–40 px (h-9 = 36px); wordmark ~18–22 px (text-xl = 20px)
  sm: {
    icon: 'h-9',
    text: 'text-xl',
    gap: 'gap-2',
    tagline: 'text-[11px]',
  },
  // Desktop sidebar & landing page header: icon 40–48 px (h-11 = 44px); wordmark ~22–26 px (text-[22px])
  md: {
    icon: 'h-11',
    text: 'text-[22px]',
    gap: 'gap-2.5',
    tagline: 'text-xs',
  },
  // Login & signup pages: icon 48–56 px (h-[52px] = 52px); wordmark ~24–28 px (text-[26px])
  lg: {
    icon: 'h-[52px]',
    text: 'text-[26px]',
    gap: 'gap-3',
    tagline: 'text-xs',
  },
};

export function Logo({
  to = '/',
  className = '',
  imageClassName = '',
  textClassName = '',
  taglineClassName = '',
  showTagline = false,
  alt = 'LearnMate',
  size = 'md',
}: LogoProps) {
  const config = SIZE_CONFIGS[size] || SIZE_CONFIGS.md;

  return (
    <Link
      to={to}
      className={`inline-flex items-center ${config.gap} group select-none ${className}`}
      aria-label={alt}
    >
      <img
        src="/LearnMate.png"
        alt={`${alt} logo`}
        className={`${config.icon} w-auto object-contain transition-transform duration-200 group-hover:scale-105 ${imageClassName}`}
      />
      <div className="flex flex-col justify-center">
        <span
          className={`whitespace-nowrap font-display font-bold tracking-tight leading-none text-ink-900 dark:text-white ${config.text} ${textClassName}`}
        >
          Learn<span className="text-brand-600 dark:text-brand-400">Mate</span>
        </span>
        {showTagline && (
          <span
            className={`font-medium text-ink-500 dark:text-ink-400 tracking-tight mt-1 leading-none ${config.tagline} ${taglineClassName}`}
          >
            Your AI-powered learning companion.
          </span>
        )}
      </div>
    </Link>
  );
}

