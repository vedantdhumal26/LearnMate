from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.course import Course
from app.schemas.tutor import TutorChatRequest, TutorChatResponse, CitationItem
from app.services.rag.retriever import CourseRetriever
from app.services.rag.prompt_builder import RAGPromptBuilder
from app.services.rag.citation import CitationBuilder
from app.services.rag.grounding import GroundingValidator, REFUSAL_MESSAGE
from app.services.llm.llm_service import get_llm_service
from app.services.rag.small_talk import get_small_talk_response
from app.core.logging_config import logger

class TutorService:
    def __init__(
        self,
        retriever: CourseRetriever = None,
        llm_service = None,
        grounding_validator: GroundingValidator = None,
        citation_builder: CitationBuilder = None,
    ):
        self.retriever = retriever or CourseRetriever()
        self.grounding_validator = grounding_validator or GroundingValidator()
        self.citation_builder = citation_builder or CitationBuilder()
        self._llm_service = llm_service

    @property
    def llm_service(self):
        if self._llm_service is not None:
            return self._llm_service
        return get_llm_service()

    def answer_question(
        self,
        request: TutorChatRequest,
        db: Session,
        request_type: str = "tutor",
        priority: Optional[int] = None
    ) -> TutorChatResponse:
        """
        Execute grounded RAG workflow:
        1. Validate course exists
        2. Semantic retrieval from Qdrant with course_id filter
        3. Pre-retrieval grounding validation
        4. Strict prompt formulation
        5. LLM answer generation
        6. Page-exact citation extraction
        7. Post-generation grounding validation
        """
        # 1. Validate course exists
        course = db.query(Course).filter(Course.id == request.course_id).first()
        if not course:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Course with ID '{request.course_id}' not found."
            )

        query_text = request.message.strip()
        if not query_text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Message cannot be empty."
            )

        # Check for conversational small talk before retrieval and LLM
        small_talk_response = get_small_talk_response(query_text)
        if small_talk_response is not None:
            logger.info(
                f"Small-talk intent handled for course {request.course_id}: "
                f"message='{query_text}'"
            )
            return small_talk_response

        # 2. Retrieve relevant chunks from Qdrant (strictly filtered by course_id)
        chunks = self.retriever.retrieve(
            course_id=request.course_id,
            query=query_text
        )

        # 3. Pre-retrieval grounding check
        is_grounded_pre, reason = self.grounding_validator.validate_pre_retrieval(chunks)
        if not is_grounded_pre:
            logger.info(f"Pre-retrieval rejection for query '{query_text}': {reason}")
            return TutorChatResponse(
                answer=REFUSAL_MESSAGE,
                grounded=False,
                sources=[],
                response_type="academic"
            )

        # 4. Build prompt
        system_prompt = RAGPromptBuilder.build_system_prompt()
        user_prompt = RAGPromptBuilder.build_user_prompt(query_text, chunks)

        # 5. Generate LLM completion with bounded output tokens and priority
        try:
            try:
                raw_answer = self.llm_service.generate(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    request_type=request_type,
                    priority=priority,
                    max_tokens=600
                )
            except TypeError as te:
                if "unexpected keyword argument" in str(te):
                    raw_answer = self.llm_service.generate(
                        prompt=user_prompt,
                        system_prompt=system_prompt
                    )
                else:
                    raise
        except HTTPException:
            raise
        except Exception as e:
            err_str = str(e).lower()
            if "429" in err_str or "rate limit" in err_str or "temporarily busy" in err_str:
                logger.warning(f"Tutor LLM rate limit: {e}")
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="AI service is temporarily busy. Please try again."
                )
            if "timeout" in err_str or "timed out" in err_str:
                logger.warning(f"Tutor LLM timeout: {e}")
                raise HTTPException(
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                    detail="AI service is temporarily busy. Please try again."
                )
            logger.error(f"Error during LLM generation: {e}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Tutor LLM service error: {str(e)}"
            )

        # 6. Build exact citations from retrieved chunks
        citations = self.citation_builder.build_citations(chunks)

        # 7. Post-generation grounding check
        is_grounded, final_answer, final_citations = self.grounding_validator.validate_post_generation(
            raw_answer, citations
        )

        logger.info(
            f"Tutor response generated for course {request.course_id}: "
            f"grounded={is_grounded}, {len(final_citations)} citations"
        )

        return TutorChatResponse(
            answer=final_answer,
            grounded=is_grounded,
            sources=final_citations,
            response_type="academic"
        )
