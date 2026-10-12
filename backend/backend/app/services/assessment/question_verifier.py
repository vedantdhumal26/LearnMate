import json
import re
from typing import Dict, Any, List, Optional, Tuple
from app.services.vector_store.base import VectorSearchResult
from app.core.logging_config import logger

class QuestionVerifier:
    """
    Validates generated assessment questions for course-grounding,
    structural integrity, single correct answer for MCQ, and arithmetic consistency for numericals.
    """

    @staticmethod
    def verify_question(
        question_data: Dict[str, Any],
        question_type: str,
        topic: str,
        retrieved_chunks: Optional[List[VectorSearchResult]] = None
    ) -> Tuple[bool, str]:
        """
        Runs comprehensive verification on a generated question dictionary.
        Returns: (is_valid: bool, reason: str)
        """
        if not isinstance(question_data, dict):
            return False, "Question data must be a dictionary."

        # 1. Basic field presence
        q_text = str(question_data.get("question", "")).strip()
        correct_ans = str(question_data.get("correct_answer", "")).strip()
        explanation = str(question_data.get("explanation", "")).strip()

        if not q_text or len(q_text) < 10:
            return False, "Question text is missing or too short."
        if not correct_ans:
            return False, "Correct answer is missing."
        if not explanation or len(explanation) < 10:
            return False, "Explanation is missing or too short."

        # Check refusal strings (model must not return a refusal as a question)
        lower_q = q_text.lower()
        if "couldn't find" in lower_q or "not enough information" in lower_q or "cannot answer" in lower_q:
            return False, "Model generated a refusal instead of a valid question."

        # 2. Context Grounding Check (executed when retrieved course context is provided)
        if retrieved_chunks:
            # Aggregate all retrieved text
            full_context = " ".join([c.content.lower() for c in retrieved_chunks if getattr(c, "content", None)])
            
            # Check that question item (question text + options + explanation) has grounding overlap with retrieved text
            content_for_grounding = f"{q_text} {topic}".lower()
            opts = question_data.get("options")
            if isinstance(opts, str):
                try:
                    opts = json.loads(opts)
                except Exception:
                    pass
            if opts and isinstance(opts, list):
                content_for_grounding += " " + " ".join(str(o) for o in opts).lower()
            if explanation:
                content_for_grounding += " " + explanation.lower()

            content_words = [w for w in re.findall(r"\b[a-zA-Z]{4,}\b", content_for_grounding)]
            if content_words:
                matched_words = [w for w in content_words if w in full_context]
                # Require at least 2 distinct conceptual terms from context or >= 15% overlap
                unique_matched = set(matched_words)
                if len(unique_matched) < 2:
                    return False, f"Question is not sufficiently grounded in course material (only {len(unique_matched)} unique terms matched)."

        # 3. Question-type specific validation
        q_type_clean = question_type.lower().strip()
        if q_type_clean == "mcq":
            options = question_data.get("options")
            if isinstance(options, str):
                try:
                    options = json.loads(options)
                except Exception:
                    pass
            if not isinstance(options, list) or len(options) != 4:
                return False, f"MCQ must have exactly 4 options. Found: {len(options) if isinstance(options, list) else 0}"
            
            # Check options are non-empty and unique
            cleaned_opts = [str(opt).strip() for opt in options]
            if any(len(opt) == 0 for opt in cleaned_opts):
                return False, "MCQ options cannot be blank."
            stripped_opts = [re.sub(r"^[A-Da-d][\)\.\:\s-]\s*", "", opt).strip().lower() for opt in cleaned_opts]
            if len(set(cleaned_opts)) != 4 or len(set(stripped_opts)) != 4:
                return False, "MCQ options must all be distinct."

            # Verify exactly one correct answer
            # Can be 'A', 'B', 'C', 'D' or exact option text
            ans_clean = correct_ans.strip()
            letters = ["A", "B", "C", "D"]
            
            # If answer is a letter A-D (e.g. "A", "A)", "A.", "A: ")
            first_char = ans_clean[0].upper() if ans_clean else ""
            matches_letter = first_char in letters and (len(ans_clean) == 1 or ans_clean[1] in [")", ".", ":", " "])
            matches_text = any(ans_clean.lower() == opt.lower() or ans_clean.lower() in opt.lower() for opt in cleaned_opts)

            if not (matches_letter or matches_text):
                return False, f"Correct answer '{correct_ans}' does not match any of the 4 options."

        elif q_type_clean == "numerical":
            # Extract numerical values
            nums_in_ans = re.findall(r"[-+]?\d*\.?\d+", correct_ans)
            if not nums_in_ans:
                return False, f"Numerical question correct_answer '{correct_ans}' does not contain a valid number."
            
            # Check arithmetic in explanation if present
            # Look for expressions like A * B = C or A + B = C
            arithmetic_pattern = re.findall(r"([\d\.]+)\s*([\+\-\*\/])\s*([\d\.]+)\s*=\s*([\d\.]+)", explanation)
            for a, op, b, c in arithmetic_pattern:
                try:
                    fa, fb, fc = float(a), float(b), float(c)
                    expected = None
                    if op == "+":
                        expected = fa + fb
                    elif op == "-":
                        expected = fa - fb
                    elif op == "*":
                        expected = fa * fb
                    elif op == "/" and fb != 0:
                        expected = fa / fb
                    if expected is not None and abs(expected - fc) > 0.05 * (abs(fc) + 1e-5):
                        return False, f"Mathematical inconsistency in explanation: {a} {op} {b} != {c}"
                except ValueError:
                    continue

        elif q_type_clean == "short_answer":
            if len(correct_ans) < 3:
                return False, "Short answer expected answer is too brief."

        # 4. Source Citation Verification (checked against retrieved chunks when provided)
        sources = question_data.get("sources", [])
        if sources and retrieved_chunks:
            valid_source_ids = {c.source_id for c in retrieved_chunks if getattr(c, "source_id", None)}
            valid_pages = {c.page_number for c in retrieved_chunks if getattr(c, "page_number", None)}
            for s in sources:
                if isinstance(s, dict):
                    sid = s.get("source_id")
                    page = s.get("page")
                    if sid and valid_source_ids and sid not in valid_source_ids:
                        return False, f"Citation source_id '{sid}' not among retrieved course sources."
                    if page and valid_pages and page not in valid_pages:
                        return False, f"Citation page {page} not among retrieved pages {valid_pages}."

        return True, "Verification passed."
