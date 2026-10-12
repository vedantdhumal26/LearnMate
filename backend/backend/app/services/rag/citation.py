from typing import List, Set
from app.services.vector_store.base import VectorSearchResult
from app.schemas.tutor import CitationItem

class CitationBuilder:
    @staticmethod
    def build_citations(
        chunks: List[VectorSearchResult],
        max_excerpt_len: int = 250
    ) -> List[CitationItem]:
        """
        Build exact citations directly from the retrieved document chunks.
        Ensures citations are strictly bound to actual stored documents and pages.
        """
        citations: List[CitationItem] = []
        seen_keys: Set[str] = set()

        for chunk in chunks:
            # Deduplicate citations by (source_id, page_number, slide_number, start_time_seconds, end_time_seconds)
            dedup_key = f"{chunk.source_id}:{chunk.page_number}:{chunk.slide_number}:{chunk.start_time_seconds}:{chunk.end_time_seconds}"
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            # Extract clean excerpt from actual content
            content_cleaned = " ".join(chunk.content.strip().split())
            if len(content_cleaned) > max_excerpt_len:
                excerpt = content_cleaned[:max_excerpt_len].rsplit(" ", 1)[0] + "..."
            else:
                excerpt = content_cleaned

            if chunk.modality == "youtube" and chunk.start_time_seconds is not None and chunk.end_time_seconds is not None:
                from app.services.transcription.transcription_service import format_timestamp
                t_start = format_timestamp(chunk.start_time_seconds)
                t_end = format_timestamp(chunk.end_time_seconds)
                header = f"[YouTube {t_start}–{t_end}]"
                if not excerpt.startswith("[YouTube"):
                    excerpt = f"{header}\n{excerpt}"

            citations.append(
                CitationItem(
                    source_id=chunk.source_id,
                    file_name=chunk.file_name,
                    page=chunk.page_number,
                    slide=chunk.slide_number,
                    start_seconds=chunk.start_time_seconds,
                    end_seconds=chunk.end_time_seconds,
                    excerpt=excerpt,
                    modality=chunk.modality,
                    video_id=chunk.video_id,
                    canonical_url=chunk.canonical_url
                )
            )

        return citations
