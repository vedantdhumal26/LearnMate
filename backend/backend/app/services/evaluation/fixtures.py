import json
import os
from typing import List, Dict, Any, Optional
from app.schemas.evaluation import EvaluationTestCase, ExpectedSource

def get_default_evaluation_dataset(
    course_id: str = "default-course",
    isolation_course_id: str = "isolation-course",
    source_mapping: Optional[Dict[str, str]] = None
) -> List[EvaluationTestCase]:
    """
    Returns a standardized, provider-independent evaluation dataset covering:
    - Supported PDF question with page citation
    - Supported PPTX question with slide citation
    - Supported MP4 video question with timestamp citation
    - Supported YouTube question with timestamp citation
    - Unsupported off-material questions (grounded=False, sources=[])
    - Cross-course isolation test cases (asking in Course B for Course A's material)
    """
    mapping = source_mapping or {}
    pdf_sid = mapping.get("pdf", "pdf-source-001")
    pptx_sid = mapping.get("pptx", "pptx-source-001")
    mp4_sid = mapping.get("mp4", "mp4-source-001")
    yt_sid = mapping.get("youtube", "youtube-source-001")

    cases = [
        # 1. PDF Supported Case
        EvaluationTestCase(
            id="eval-pdf-001",
            course_id=course_id,
            question="What is Newton's second law of motion and what is its mathematical formula?",
            expected_answer="The acceleration of an object is directly proportional to the net force and inversely proportional to its mass: F = m * a.",
            expected_grounded=True,
            expected_sources=[
                ExpectedSource(
                    source_id=pdf_sid,
                    page=2,
                    modality="pdf"
                )
            ]
        ),
        # 2. PPTX Supported Case
        EvaluationTestCase(
            id="eval-pptx-001",
            course_id=course_id,
            question="According to the presentation slides, what are the three main components of an electric motor?",
            expected_answer="Stator, rotor, and commutator.",
            expected_grounded=True,
            expected_sources=[
                ExpectedSource(
                    source_id=pptx_sid,
                    slide=2,
                    modality="pptx"
                )
            ]
        ),
        # 3. MP4 Video Supported Case
        EvaluationTestCase(
            id="eval-mp4-001",
            course_id=course_id,
            question="According to Bernoulli's principle in the fluid mechanics lecture video, what happens to pressure when velocity increases?",
            expected_answer="When fluid velocity increases, static pressure decreases.",
            expected_grounded=True,
            expected_sources=[
                ExpectedSource(
                    source_id=mp4_sid,
                    start_seconds=0.0,
                    end_seconds=30.0,
                    modality="video"
                )
            ]
        ),
        # 4. YouTube Supported Case
        EvaluationTestCase(
            id="eval-yt-001",
            course_id=course_id,
            question="How many neurons make up the input layer of the neural network for a 28 by 28 pixel image?",
            expected_answer="784 neurons correspond to the 784 pixels (28 times 28) in the input layer.",
            expected_grounded=True,
            expected_sources=[
                ExpectedSource(
                    source_id=yt_sid,
                    start_seconds=180.0,
                    end_seconds=240.0,
                    modality="youtube"
                )
            ]
        ),
        # 5. Unsupported Question Case (Out-of-domain)
        EvaluationTestCase(
            id="eval-unsupported-001",
            course_id=course_id,
            question="What is the capital of ancient Mesopotamia and what were the complete laws of Hammurabi?",
            expected_answer=None,
            expected_grounded=False,
            expected_sources=[]
        ),
        # 6. Unsupported Question Case 2 (Fictional / Unrelated)
        EvaluationTestCase(
            id="eval-unsupported-002",
            course_id=course_id,
            question="What are the official tournament rules and scoring of professional cricket?",
            expected_answer=None,
            expected_grounded=False,
            expected_sources=[]
        ),
        # 7. Course Isolation Leakage Test Case
        EvaluationTestCase(
            id="eval-isolation-001",
            course_id=isolation_course_id,  # Query submitted against empty Course B
            question="What is Newton's second law and the formula from the physics document?",
            expected_answer=None,
            expected_grounded=False,
            expected_sources=[],
            is_course_isolation=True,
            source_course_id=course_id  # Content exists in Course A
        ),
    ]

    return cases

def load_dataset_from_file_or_default(
    file_path: Optional[str] = None,
    course_id: Optional[str] = None,
    db = None
) -> List[EvaluationTestCase]:
    """Load evaluation test cases from a JSON file, or fallback to the 40-case benchmark or default dataset."""
    chosen_path = file_path
    if not chosen_path:
        default_bench_path = os.path.join(os.path.dirname(__file__), "benchmark_dataset_phase5b.json")
        if os.path.exists(default_bench_path):
            chosen_path = default_bench_path

    if chosen_path and os.path.exists(chosen_path):
        with open(chosen_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
        if isinstance(raw_data, list):
            items = []
            for item in raw_data:
                items.append(EvaluationTestCase.model_validate(item))
            return items

    target_course = course_id or "default-course"
    return get_default_evaluation_dataset(course_id=target_course)
