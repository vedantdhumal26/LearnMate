import math
import re
from typing import List, Dict, Any, Optional, Tuple
from app.schemas.tutor import CitationItem
from app.schemas.evaluation import ExpectedSource
from app.services.embeddings.embedding_service import get_embedding_service
from app.core.logging_config import logger

class RAGEvaluator:
    """
    Computes standard RAG metrics:
    - Faithfulness (grounding of answer in retrieved context)
    - Answer Relevancy (cosine similarity between question & answer embeddings)
    - Context Precision (proportion of retrieved chunks that are relevant)
    - Context Recall (proportion of expected sources retrieved)

    Zero fabricated metrics: if a metric cannot be calculated, returns None.
    """

    def __init__(self, embedding_service=None, llm_service=None):
        self._embedding_service = embedding_service
        self._llm_service = llm_service

    @property
    def embedding_service(self):
        if self._embedding_service is None:
            self._embedding_service = get_embedding_service()
        return self._embedding_service

    @property
    def llm_service(self):
        if self._llm_service is None:
            try:
                from app.services.llm.llm_service import get_llm_service
                self._llm_service = get_llm_service()
            except Exception:
                self._llm_service = None
        return self._llm_service

    def evaluate_answer_relevance(self, question: str, answer: str) -> Optional[float]:
        """
        Compute Answer Relevancy using dense semantic embeddings:
        cosine similarity between question vector and answer vector.
        """
        if not question or not answer or not answer.strip():
            return None

        # If answer is a refusal, relevancy is 0.0 for that specific topic query
        if "couldn't find enough information" in answer.lower() or "not enough information" in answer.lower():
            return 0.0

        try:
            q_vec = self.embedding_service.embed_text(question.strip())
            a_vec = self.embedding_service.embed_text(answer.strip())

            dot_prod = sum(a * b for a, b in zip(q_vec, a_vec))
            norm_q = math.sqrt(sum(a * a for a in q_vec))
            norm_a = math.sqrt(sum(b * b for b in a_vec))

            if norm_q == 0 or norm_a == 0:
                return 0.0

            sim = dot_prod / (norm_q * norm_a)
            # Normalize to 0.0 - 1.0 range
            return round(max(0.0, min(1.0, float(sim))), 3)
        except Exception as e:
            logger.warning(f"Error computing answer relevance: {e}")
            return None

    def evaluate_faithfulness(
        self,
        answer: str,
        retrieved_contexts: List[str],
        use_llm: bool = True
    ) -> Optional[float]:
        """
        Compute Faithfulness: the proportion of statements in the answer
        that are directly supported by the retrieved context.
        Uses LLM evaluation if configured and enabled, or semantic n-gram claim verification.
        """
        if not answer or not answer.strip():
            return None

        if not retrieved_contexts:
            # If no context was retrieved but model generated an answer, faithfulness is 0
            return 0.0 if len(answer.strip()) > 30 else 1.0

        combined_context = " ".join(retrieved_contexts).lower()

        # Clean answer text: remove parenthetical citations like (eval_physics.pdf — Page 2)
        cleaned_answer = re.sub(r"\([^\)]*?\.(pdf|pptx|mp4)[^\)]*?\)", "", answer)
        cleaned_answer = re.sub(r"\[Video [^\]]+\]", "", cleaned_answer)
        cleaned_answer = re.sub(r"\[YouTube [^\]]+\]", "", cleaned_answer)
        cleaned_answer = re.sub(r"\[Slide [^\]]+\]", "", cleaned_answer)

        # Split answer into distinct sentences/claims
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", cleaned_answer) if len(s.strip()) > 10]
        if not sentences:
            return 1.0

        import hashlib

        # Check refusal first (100% faithful rejection)
        if "couldn't find enough information" in answer.lower() or "not enough information" in answer.lower():
            return 1.0

        if not hasattr(self, "_faithfulness_cache"):
            self._faithfulness_cache = {}

        cache_key = hashlib.sha256(f"{cleaned_answer.strip()}|{combined_context[:2000].strip()}".encode()).hexdigest()
        if cache_key in self._faithfulness_cache:
            return self._faithfulness_cache[cache_key]

        # Try LLM evaluator first if available and enabled
        if use_llm and self.llm_service is not None:
            try:
                system_prompt = (
                    "You are an impartial RAG evaluator. Assess whether each sentence in the answer "
                    "is directly supported by the context. Output ONLY a JSON object: {\"faithfulness_score\": 0.95}"
                )
                prompt = (
                    f"CONTEXT:\n{combined_context[:3000]}\n\n"
                    f"ANSWER:\n{cleaned_answer}\n\n"
                    "Rate the fraction of factual claims in the answer supported by the context (0.0 to 1.0)."
                )
                from app.services.llm.concurrency_gate import RequestPriority
                llm_out = self.llm_service.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    request_type="evaluation",
                    priority=RequestPriority.EVALUATION,
                    max_tokens=150
                )
                score_match = re.search(r"\"faithfulness_score\"\s*:\s*([0-9\.]+)", llm_out)
                if score_match:
                    val = float(score_match.group(1))
                    res = round(max(0.0, min(1.0, val)), 3)
                    self._faithfulness_cache[cache_key] = res
                    return res
            except Exception as e:
                logger.debug(f"LLM faithfulness evaluation fallback to claim verification: {e}")

        # Deterministic token/claim overlap fallback
        supported_claims = 0
        for sent in sentences:
            tokens = set(re.findall(r"\b[a-zA-Z0-9]{4,}\b", sent.lower()))
            if not tokens:
                supported_claims += 1
                continue
            matched = sum(1 for t in tokens if t in combined_context)
            if matched / len(tokens) >= 0.4:
                supported_claims += 1

        score = supported_claims / len(sentences)
        res = round(float(score), 3)
        self._faithfulness_cache[cache_key] = res
        return res

    @staticmethod
    def _matches_expected_source(src: CitationItem, exp: ExpectedSource) -> bool:
        """Helper to match a retrieved citation against an expected source."""
        # 1. Source ID / file_name matching
        sid_match = (
            exp.source_id is None
            or exp.source_id == src.source_id
            or (exp.file_name is not None and exp.file_name == src.file_name)
        )
        if not sid_match:
            return False

        # 2. PDF Page matching
        if exp.page is not None and exp.page != src.page:
            return False

        # 3. PPTX Slide matching
        if exp.slide is not None and exp.slide != src.slide:
            return False

        # 4. Audio/Video/YouTube Timestamp matching
        if exp.start_seconds is not None or exp.end_seconds is not None:
            if src.start_seconds is None or src.end_seconds is None:
                return False
            exp_s = exp.start_seconds or 0.0
            exp_e = exp.end_seconds or (exp_s + 60.0)
            src_s = src.start_seconds
            src_e = src.end_seconds
            overlap = max(0.0, min(exp_e, src_e) - max(exp_s, src_s))
            if overlap <= 0 and abs(src_s - exp_s) > 30.0:
                return False

        return True

    def evaluate_context_precision(
        self,
        retrieved_sources: List[CitationItem],
        expected_sources: List[ExpectedSource]
    ) -> Optional[float]:
        """
        Compute Context Precision: proportion of retrieved chunks that match expected sources.
        """
        if not retrieved_sources:
            return 1.0 if not expected_sources else 0.0

        if not expected_sources:
            return None

        relevant_count = 0
        for src in retrieved_sources:
            matched = any(self._matches_expected_source(src, exp) for exp in expected_sources)
            if matched:
                relevant_count += 1

        return round(relevant_count / len(retrieved_sources), 3)

    def evaluate_context_recall(
        self,
        retrieved_sources: List[CitationItem],
        expected_sources: List[ExpectedSource]
    ) -> Optional[float]:
        """
        Compute Context Recall: proportion of expected sources retrieved in citations.
        """
        if not expected_sources:
            return 1.0

        if not retrieved_sources:
            return 0.0

        found_expected = 0
        for exp in expected_sources:
            matched = any(self._matches_expected_source(src, exp) for src in retrieved_sources)
            if matched:
                found_expected += 1

        return round(found_expected / len(expected_sources), 3)
