import io
import pytest
from app.api.routes.tutor import tutor_service
from app.services.rag.small_talk import (
    GREETING_RESPONSE,
    THANKS_RESPONSE,
    FAREWELL_RESPONSE,
    classify_small_talk,
    normalize_text,
)
from app.models.user import User
from app.models.course import Course
from app.utils.password import hash_password
from app.core.jwt import create_access_token
from tests.conftest import MockLLMService


class TrackingMockLLM(MockLLMService):
    def __init__(self, response_text: str = "Mock answer"):
        super().__init__(response_text=response_text)
        self.call_count = 0
        self.last_prompt = None

    def generate(self, prompt: str, system_prompt: str = None, *args, **kwargs) -> str:
        self.call_count += 1
        self.last_prompt = prompt
        return self.response_text


class FailingLLM(MockLLMService):
    def generate(self, prompt: str, system_prompt: str = None, *args, **kwargs) -> str:
        raise AssertionError("LLM should not have been called!")


@pytest.fixture
def created_course_id(client):
    res = client.post("/api/courses", json={"title": "Physics 101"})
    assert res.status_code == 201
    return res.json()["id"]


# -----------------------------------------------------------------------------
# 1. Deterministic greetings
# -----------------------------------------------------------------------------

def test_greeting_hi_receives_friendly_response(client, created_course_id):
    """Test 1: 'Hi' receives a friendly response."""
    payload = {"course_id": created_course_id, "message": "Hi"}
    res = client.post("/api/tutor/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["answer"] == GREETING_RESPONSE
    assert data["grounded"] is False
    assert data["sources"] == []
    assert data["response_type"] in ("small_talk", "conversational")


def test_greeting_hello_exclamation_receives_friendly_response(client, created_course_id):
    """Test 2: 'Hello!' receives a friendly response."""
    payload = {"course_id": created_course_id, "message": "Hello!"}
    res = client.post("/api/tutor/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["answer"] == GREETING_RESPONSE
    assert data["grounded"] is False
    assert data["sources"] == []
    assert data["response_type"] in ("small_talk", "conversational")


def test_greeting_how_are_you_receives_friendly_response(client, created_course_id):
    """Test 3: 'How are you?' receives a friendly response."""
    payload = {"course_id": created_course_id, "message": "How are you?"}
    res = client.post("/api/tutor/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["answer"] == GREETING_RESPONSE
    assert data["grounded"] is False
    assert data["sources"] == []
    assert data["response_type"] in ("small_talk", "conversational")


def test_courtesy_thank_you_receives_acknowledgement(client, created_course_id):
    """Test 4: 'Thank you' receives an appropriate acknowledgement."""
    payload = {"course_id": created_course_id, "message": "Thank you"}
    res = client.post("/api/tutor/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["answer"] == THANKS_RESPONSE
    assert data["grounded"] is False
    assert data["sources"] == []
    assert data["response_type"] in ("small_talk", "conversational")


def test_courtesy_bye_receives_farewell(client, created_course_id):
    """Test 5: 'Bye' receives a farewell."""
    payload = {"course_id": created_course_id, "message": "Bye"}
    res = client.post("/api/tutor/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["answer"] == FAREWELL_RESPONSE
    assert data["grounded"] is False
    assert data["sources"] == []
    assert data["response_type"] in ("small_talk", "conversational")


# -----------------------------------------------------------------------------
# 2. Zero LLM calls and No Fabricated Sources
# -----------------------------------------------------------------------------

def test_greetings_do_not_invoke_llm(client, created_course_id):
    """Test 6: Greetings do not invoke the LLM (zero LLM calls guaranteed)."""
    failing_llm = FailingLLM()
    tutor_service._llm_service = failing_llm

    greetings = [
        "Hi",
        "Hello!",
        "Hey",
        "Good morning",
        "Good afternoon",
        "Good evening",
        "How are you?",
        "Thanks",
        "Thank you",
        "Bye",
        "Goodbye",
        "See you",
    ]

    try:
        for msg in greetings:
            res = client.post("/api/tutor/chat", json={"course_id": created_course_id, "message": msg})
            assert res.status_code == 200
            assert res.json()["response_type"] in ("small_talk", "conversational")
    finally:
        tutor_service._llm_service = None


def test_greeting_responses_contain_no_fabricated_sources(client, created_course_id):
    """Test 7: Greeting responses contain no fabricated sources."""
    for phrase in ["Hi", "Hello!", "How are you?", "Thank you", "Goodbye", "  hey there! "]:
        res = client.post("/api/tutor/chat", json={"course_id": created_course_id, "message": phrase})
        assert res.status_code == 200
        data = res.json()
        assert data["sources"] == []
        assert len(data["sources"]) == 0
        assert data["grounded"] is False


# -----------------------------------------------------------------------------
# 3. Mixed Academic Questions & RAG Pipeline Preservation
# -----------------------------------------------------------------------------

def test_mixed_academic_question_uses_rag(client, sample_physics_pdf):
    """Test 8: 'Hi, explain Newton's second law' uses RAG (does not intercept)."""
    # 1. Create course and upload PDF
    c_res = client.post("/api/courses", json={"title": "Physics 101"})
    course_id = c_res.json()["id"]

    files = {"file": ("newton_laws.pdf", io.BytesIO(sample_physics_pdf), "application/pdf")}
    up_res = client.post(f"/api/courses/{course_id}/upload", files=files)
    assert up_res.status_code == 201

    # 2. Track LLM calls
    tracking_llm = TrackingMockLLM(
        response_text="Newton's second law states that Force equals mass times acceleration (F = ma)."
    )
    tutor_service._llm_service = tracking_llm

    try:
        # 3. Mixed query with greeting prefix
        payload = {
            "course_id": course_id,
            "message": "Hi, explain Newton's second law"
        }
        res = client.post("/api/tutor/chat", json=payload)
        assert res.status_code == 200
        data = res.json()

        # LLM must be called
        assert tracking_llm.call_count == 1
        assert "Newton's second law" in data["answer"]
        assert data["grounded"] is True
        assert len(data["sources"]) > 0
        assert data["sources"][0]["file_name"] == "newton_laws.pdf"
        assert data["response_type"] == "academic"
    finally:
        tutor_service._llm_service = None


def test_mixed_courtesy_questions_use_rag(client, sample_physics_pdf):
    """Test that other mixed messages with thanks or greetings continue to RAG."""
    c_res = client.post("/api/courses", json={"title": "Physics 101"})
    course_id = c_res.json()["id"]
    files = {"file": ("newton_laws.pdf", io.BytesIO(sample_physics_pdf), "application/pdf")}
    client.post(f"/api/courses/{course_id}/upload", files=files)

    tracking_llm = TrackingMockLLM(
        response_text="Force is defined as F = m * a."
    )
    tutor_service._llm_service = tracking_llm

    try:
        mixed_queries = [
            "Hello, what is the formula for force?",
            "Thanks. Can you explain that equation again?",
        ]
        for query in mixed_queries:
            tracking_llm.call_count = 0
            res = client.post("/api/tutor/chat", json={"course_id": course_id, "message": query})
            assert res.status_code == 200
            assert tracking_llm.call_count == 1
            data = res.json()
            assert data["response_type"] == "academic"
    finally:
        tutor_service._llm_service = None


def test_unsupported_academic_questions_still_rejected(client, sample_physics_pdf):
    """Test 9: Unsupported academic questions are still rejected by grounding safeguards."""
    c_res = client.post("/api/courses", json={"title": "Physics 101"})
    course_id = c_res.json()["id"]
    files = {"file": ("newton_laws.pdf", io.BytesIO(sample_physics_pdf), "application/pdf")}
    client.post(f"/api/courses/{course_id}/upload", files=files)

    mock_refusal = MockLLMService(
        response_text="I couldn't find enough information about this topic in the uploaded course material."
    )
    tutor_service._llm_service = mock_refusal

    try:
        # Off-material query
        payload = {
            "course_id": course_id,
            "message": "How does chlorophyll absorb light during plant photosynthesis?"
        }
        res = client.post("/api/tutor/chat", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["grounded"] is False
        assert data["sources"] == []
        assert "couldn't find enough information" in data["answer"]
        assert data["response_type"] == "academic"
    finally:
        tutor_service._llm_service = None


# -----------------------------------------------------------------------------
# 4. Course Isolation & Authorization
# -----------------------------------------------------------------------------

def test_course_isolation_and_ownership_unchanged(client, unauthenticated_client, db_session, sample_physics_pdf):
    """Test 10: Course isolation and authenticated ownership remain unchanged."""
    # 1. Unauthenticated greeting must fail with 401
    res = unauthenticated_client.post("/api/tutor/chat", json={"course_id": "any-course", "message": "Hi"})
    assert res.status_code == 401

    # 2. Non-existent course greeting must fail with 404
    res = client.post("/api/tutor/chat", json={"course_id": "non-existent-course-id", "message": "Hi"})
    assert res.status_code == 404

    # 3. Course owned by another user cannot be accessed even with greeting
    other_user = User(
        id="user-other-999",
        email="other@learnsphere.test",
        password_hash=hash_password("Password123!"),
        display_name="Other User"
    )
    db_session.add(other_user)
    db_session.commit()

    other_course = Course(
        id="course-other-888",
        title="Other Course",
        owner_id=other_user.id
    )
    db_session.add(other_course)
    db_session.commit()

    # Current client (default_user) trying to access other_user's course with greeting
    res = client.post("/api/tutor/chat", json={"course_id": "course-other-888", "message": "Hello!"})
    assert res.status_code == 404

    # 4. Isolation: Empty course queries do not leak from another course
    c_a_res = client.post("/api/courses", json={"title": "Physics Course"})
    course_a_id = c_a_res.json()["id"]
    files = {"file": ("newton_laws.pdf", io.BytesIO(sample_physics_pdf), "application/pdf")}
    client.post(f"/api/courses/{course_a_id}/upload", files=files)

    c_b_res = client.post("/api/courses", json={"title": "Empty Literature Course"})
    course_b_id = c_b_res.json()["id"]

    res = client.post("/api/tutor/chat", json={"course_id": course_b_id, "message": "Explain Newton's second law"})
    assert res.status_code == 200
    assert res.json()["grounded"] is False
    assert res.json()["sources"] == []


# -----------------------------------------------------------------------------
# 5. Unit Tests for Normalization and Classification
# -----------------------------------------------------------------------------

def test_normalization_and_punctuation_handling():
    """Verify robust normalization of whitespace, case, and harmless punctuation."""
    assert normalize_text("   Hi   ") == "hi"
    assert normalize_text("HELLO!") == "hello"
    assert normalize_text("How are you???") == "how are you"
    assert normalize_text("Good   morning...") == "good morning"
    assert normalize_text("!hey!") == "hey"
    assert normalize_text("'thank you'") == "thank you"
    assert normalize_text("bye-bye") == "bye-bye"


def test_classify_small_talk_coverage():
    """Verify intent classifications."""
    assert classify_small_talk("hi") == "greeting"
    assert classify_small_talk("Hello!") == "greeting"
    assert classify_small_talk("Good morning") == "greeting"
    assert classify_small_talk("Good afternoon!") == "greeting"
    assert classify_small_talk("Good evening.") == "greeting"
    assert classify_small_talk("How are you?") == "greeting"
    assert classify_small_talk("how's it going?") == "greeting"
    assert classify_small_talk("hows it going") == "greeting"

    assert classify_small_talk("Thanks") == "thanks"
    assert classify_small_talk("Thank you!") == "thanks"
    assert classify_small_talk("thanks a lot") == "thanks"

    assert classify_small_talk("bye") == "farewell"
    assert classify_small_talk("Goodbye!") == "farewell"
    assert classify_small_talk("See you") == "farewell"
    assert classify_small_talk("see you later!") == "farewell"

    # Negative cases
    assert classify_small_talk("Hi, what is physics?") is None
    assert classify_small_talk("Explain Newton's law") is None
    assert classify_small_talk("What is force?") is None
    assert classify_small_talk("Photosynthesis") is None
    assert classify_small_talk("") is None
