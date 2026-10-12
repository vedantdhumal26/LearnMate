import { CitationCard } from '@/components/CitationCard';
import type { TutorSource } from '@/types';

export function SourceCard({ source, index }: { source: TutorSource; index: number }) {
  return <CitationCard source={source} index={index} />;
}
