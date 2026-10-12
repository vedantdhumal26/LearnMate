from typing import List
from app.services.vector_store.base import VectorSearchResult

class RAGPromptBuilder:
    @staticmethod
    def build_system_prompt() -> str:
        """
        Build the strict tutor system prompt as specified in Milestone Section 14.
        """
        return (
            "You are a course-material tutor for LearnSphere AI.\n\n"
            "CRITICAL INSTRUCTIONS:\n"
            "1. Answer the student's question using ONLY the supplied course context below.\n"
            "2. Do not invent facts. Do not invent citations.\n"
            "3. Do not claim information exists in the course material unless the retrieved context directly supports it.\n"
            "4. If the supplied course context is insufficient or off-topic, clearly say:\n"
            "   \"I couldn't find enough information about this topic in the uploaded course material.\"\n"
            "5. When answering, use the retrieved source material as your primary evidence.\n"
            "6. When referring to sources in your explanation, cite the source file and:\n"
            "   - for PDF: page number (e.g. 'document.pdf — Page 3')\n"
            "   - for PPTX: slide number (e.g. 'presentation.pptx — Slide 7')\n"
            "   - for Video: timestamp range (e.g. 'lecture1.mp4 — 00:04:32–00:04:49')\n"
            "   - for YouTube: timestamp range (e.g. '[YouTube 00:03:42–00:04:15]')\n"
            "   as provided in the context.\n"
            "7. Explain clearly and helpfully, maintaining an encouraging and instructional tone."
        )

    @staticmethod
    def build_user_prompt(question: str, chunks: List[VectorSearchResult]) -> str:
        """
        Format retrieved course material chunks and the student question.
        """
        from app.services.transcription.transcription_service import format_timestamp
        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            if chunk.start_time_seconds is not None and chunk.end_time_seconds is not None:
                t_str = f"{format_timestamp(chunk.start_time_seconds)}–{format_timestamp(chunk.end_time_seconds)}"
                location_str = f"Timestamp: {t_str} (Start: {chunk.start_time_seconds:.1f}s, End: {chunk.end_time_seconds:.1f}s)"
            elif chunk.slide_number is not None:
                location_str = f"Slide Number: {chunk.slide_number}"
            elif chunk.page_number is not None:
                location_str = f"Page Number: {chunk.page_number}"
            else:
                location_str = "Location: N/A"

            modality_str = f"\nModality: {chunk.modality}" if chunk.modality else ""
            context_parts.append(
                f"--- CONTEXT CHUNK {i} ---\n"
                f"Source File: {chunk.file_name}\n"
                f"{location_str}"
                f"{modality_str}\n"
                f"Content:\n{chunk.content.strip()}\n"
            )

        context_str = "\n".join(context_parts)

        return (
            f"RELEVANT COURSE MATERIAL:\n"
            f"{context_str}\n\n"
            f"STUDENT QUESTION:\n"
            f"{question.strip()}\n\n"
            f"TUTOR RESPONSE:"
        )
