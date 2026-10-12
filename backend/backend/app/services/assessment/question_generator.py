import json
import re
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.core.config import settings
from app.core.logging_config import logger
from app.services.rag.retriever import CourseRetriever
from app.services.rag.citation import CitationBuilder
from app.services.rag.grounding import GroundingValidator
from app.services.llm.llm_service import get_llm_service, LLMService
from app.services.assessment.question_verifier import QuestionVerifier
from app.services.assessment.deduplication import QuestionDeduplicator, compute_content_hash
from app.models.assessment import Question

class AssessmentQuestionGenerator:
    """
    RAG-grounded assessment question generator.
    Retrieves course materials, formats prompts, calls LLM, verifies each question,
    performs deduplication, and persists valid questions.
    """
    def __init__(
        self,
        retriever: Optional[CourseRetriever] = None,
        llm_service: Optional[LLMService] = None,
        verifier: Optional[QuestionVerifier] = None,
        deduplicator: Optional[QuestionDeduplicator] = None,
        citation_builder: Optional[CitationBuilder] = None,
        grounding_validator: Optional[GroundingValidator] = None,
    ):
        self.retriever = retriever or CourseRetriever()
        self._llm_service = llm_service
        self.verifier = verifier or QuestionVerifier()
        self.deduplicator = deduplicator or QuestionDeduplicator()
        self.citation_builder = citation_builder or CitationBuilder()
        self.grounding_validator = grounding_validator or GroundingValidator()

    @property
    def llm_service(self) -> LLMService:
        if self._llm_service is None:
            self._llm_service = get_llm_service()
        return self._llm_service

    def generate_questions(
        self,
        db: Session,
        course_id: str,
        topic: str,
        difficulty: str = "medium",
        question_type: str = "mcq",
        count: int = 5,
        student_id: Optional[str] = None,
        max_retries: int = 3,
    ) -> List[Question]:
        """
        Generate grounded assessment questions.
        1. Retrieve course context using CourseRetriever.
        2. Verify grounding threshold.
        3. Prompt LLM for structured questions.
        4. Verify and deduplicate each question.
        5. Persist to DB and return.
        """
        # 1. Retrieve course context
        chunks = self.retriever.retrieve(
            course_id=course_id,
            query=topic,
            top_k=max(settings.RAG_TOP_K, 6)
        )

        # 2. Check grounding
        is_grounded_pre, reason = self.grounding_validator.validate_pre_retrieval(chunks)
        if not is_grounded_pre or not chunks:
            logger.warning(
                f"Insufficient course material for topic '{topic}' in course '{course_id}': {reason}"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient course material found for topic '{topic}' to generate assessment questions."
            )

        # Build citations from retrieved chunks
        built_citations = self.citation_builder.build_citations(chunks)
        serialized_citations = [c.model_dump() for c in built_citations]

        # 3. Context string for LLM
        context_lines = []
        for i, chunk in enumerate(chunks, 1):
            context_lines.append(
                f"--- CONTEXT CHUNK {i} (Source: {chunk.file_name}, Page: {chunk.page_number}) ---\n"
                f"{chunk.content.strip()}"
            )
        context_str = "\n\n".join(context_lines)

        verified_questions: List[Question] = []
        attempts = 0

        while len(verified_questions) < count and attempts < max_retries:
            attempts += 1
            needed = count - len(verified_questions)

            try:
                raw_response = self._call_llm_for_questions(
                    context=context_str,
                    topic=topic,
                    difficulty=difficulty,
                    question_type=question_type,
                    count=needed,
                    attempt=attempts
                )
            except HTTPException:
                raise
            except Exception as e:
                err_str = str(e).lower()
                if "429" in err_str or "rate limit" in err_str or "temporarily busy" in err_str:
                    logger.warning(f"Assessment question generation hit rate limit: {e}")
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="AI service is temporarily busy. Please try again."
                    )
                if "timeout" in err_str or "timed out" in err_str:
                    logger.warning(f"Assessment question generation timed out: {e}")
                    raise HTTPException(
                        status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                        detail="AI service is temporarily busy. Please try again."
                    )
                logger.warning(f"Question generation LLM attempt {attempts} failed: {e}")
                continue

            parsed_list = self._parse_json_response(raw_response)
            if not parsed_list:
                logger.warning(f"Could not parse valid JSON questions from LLM attempt {attempts}")
                continue

            for q_data in parsed_list:
                if len(verified_questions) >= count:
                    break

                # Attach source citations
                if not q_data.get("sources"):
                    q_data["sources"] = serialized_citations

                # Verify question
                is_valid, v_reason = self.verifier.verify_question(
                    question_data=q_data,
                    question_type=question_type,
                    topic=topic,
                    retrieved_chunks=chunks
                )
                if not is_valid:
                    logger.info(f"Question verification rejected on attempt {attempts}: {v_reason}")
                    continue

                q_text = str(q_data.get("question", "")).strip()

                # Deduplication check
                if self.deduplicator.is_duplicate(
                    db=db,
                    course_id=course_id,
                    question_text=q_text,
                    student_id=student_id
                ):
                    logger.info(f"Duplicate question rejected: '{q_text[:40]}...'")
                    continue

                # Also avoid duplicates within the current generation batch
                q_hash = compute_content_hash(q_text)
                if any(vq.content_hash == q_hash for vq in verified_questions):
                    continue

                # Create and persist Question model
                options_list = q_data.get("options")
                if isinstance(options_list, list):
                    options_list = [str(o).strip() for o in options_list]

                question_obj = Question(
                    course_id=course_id,
                    topic_id=topic,
                    question_type=question_type.lower().strip(),
                    question_text=q_text,
                    options=options_list,
                    correct_answer=str(q_data.get("correct_answer", "")).strip(),
                    explanation=str(q_data.get("explanation", "")).strip(),
                    difficulty=difficulty.lower().strip(),
                    source_ids=q_data.get("sources", serialized_citations),
                    content_hash=q_hash
                )
                db.add(question_obj)
                db.flush()  # assign ID
                verified_questions.append(question_obj)

        if not verified_questions:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unable to generate verified course-grounded questions. Please retry."
            )

        db.commit()
        return verified_questions

    def _call_llm_for_questions(
        self,
        context: str,
        topic: str,
        difficulty: str,
        question_type: str,
        count: int,
        attempt: int = 1
    ) -> str:
        q_type_str = question_type.lower().strip()

        if q_type_str == "mcq":
            type_instructions = (
                f"Generate exactly {count} Multiple Choice Questions (MCQ).\n"
                "Requirements for each MCQ:\n"
                "- Exactly 4 plausible and distinct choices under 'options' (e.g. [\"A) ...\", \"B) ...\", \"C) ...\", \"D) ...\"]).\n"
                "- 'correct_answer' must be the single correct choice identifier (e.g. \"B\").\n"
                "- Exactly one option must be unambiguously correct according to the context.\n"
                "- 'explanation' explaining why the correct answer is right and why others are wrong."
            )
        elif q_type_str == "numerical":
            type_instructions = (
                f"Generate exactly {count} numerical problem(s) grounded strictly in formulas, relations, or values found in the course material.\n"
                "Requirements for each numerical question:\n"
                "- The problem statement must give all necessary numeric values or constants.\n"
                "- 'correct_answer' must be the exact numerical value (e.g. '10' or '9.8 m/s^2').\n"
                "- 'options' should be null.\n"
                "- 'explanation' MUST show the complete step-by-step arithmetic verifying the calculation."
            )
        else:  # short_answer
            type_instructions = (
                f"Generate exactly {count} short answer question(s).\n"
                "Requirements for each question:\n"
                "- Clear question asking for conceptual explanation directly stated in the context.\n"
                "- 'options' should be null.\n"
                "- 'correct_answer' is the comprehensive expected answer based on course context.\n"
                "- 'explanation' provides context on the expected points."
            )

        prompt = (
            f"You are an expert assessment generator for LearnSphere AI.\n\n"
            f"SOURCE COURSE MATERIAL:\n"
            f"{context}\n\n"
            f"TASK:\n"
            f"Generate {count} {difficulty}-level {question_type} question(s) on topic '{topic}'.\n\n"
            f"{type_instructions}\n\n"
            "CRITICAL RULES:\n"
            "1. ONLY use information stated in the SOURCE COURSE MATERIAL above.\n"
            "2. Never invent facts, formulas, or details not present in the source.\n"
            "3. If attempt > 1, provide distinct variations of questions to avoid repetition.\n"
            "4. Return ONLY a valid JSON array of objects. Do not write introductory or concluding prose.\n\n"
            "JSON Format:\n"
            "[\n"
            "  {\n"
            "    \"question\": \"...\",\n"
            "    \"options\": [\"A) ...\", \"B) ...\", \"C) ...\", \"D) ...\"],\n"
            "    \"correct_answer\": \"...\",\n"
            "    \"explanation\": \"...\",\n"
            "    \"difficulty\": \"" + difficulty + "\",\n"
            "    \"topic\": \"" + topic + "\"\n"
            "  }\n"
            "]"
        )

        system_prompt = (
            "You are a strict, factual academic examiner for LearnSphere AI. "
            "You output strictly valid JSON format conforming to the requested schema. "
            "Never invent facts outside the provided course text."
        )

        max_tokens_budget = min(2048, max(350, count * 220 + 100))
        try:
            return self.llm_service.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                request_type="assessment",
                max_tokens=max_tokens_budget
            )
        except TypeError as te:
            if "unexpected keyword argument" in str(te):
                return self.llm_service.generate(prompt=prompt, system_prompt=system_prompt)
            raise

    @staticmethod
    def _parse_json_response(raw_text: str) -> List[Dict[str, Any]]:
        if not raw_text:
            return []

        cleaned = raw_text.strip()
        # Remove Markdown fences if present
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
            cleaned = cleaned.strip()

        # Find first '[' and last ']'
        start_idx = cleaned.find("[")
        end_idx = cleaned.rfind("]")
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            cleaned = cleaned[start_idx : end_idx + 1]

        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, list):
                return parsed
            elif isinstance(parsed, dict):
                return [parsed]
        except Exception as e:
            logger.warning(f"JSON parsing error: {e}. Raw content: {cleaned[:100]}...")

        return []
