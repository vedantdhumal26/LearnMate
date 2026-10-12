import io
from app.api.routes.tutor import tutor_service
from tests.conftest import MockLLMService

def test_tutor_grounded_answer_and_citations(client, sample_physics_pdf):
    """
    Test grounded tutor question answering:
    - course material is retrieved
    - answer is generated
    - grounded = true
    - exact page citation is returned (page 2 for second law)
    """
    # 1. Create course and upload physics document
    c_res = client.post("/api/courses", json={"title": "Physics 101"})
    course_id = c_res.json()["id"]

    files = {"file": ("newton_laws.pdf", io.BytesIO(sample_physics_pdf), "application/pdf")}
    up_res = client.post(f"/api/courses/{course_id}/upload", files=files)
    assert up_res.status_code == 201
    source_id = up_res.json()["source_id"]

    # Inject mock LLM to guarantee deterministic test execution without billable external API calls
    mock_llm = MockLLMService(
        response_text="Newton's second law states that Force equals mass times acceleration (F = m * a)."
    )
    tutor_service._llm_service = mock_llm

    # 2. Ask question clearly answered by Page 2 of the PDF
    chat_payload = {
        "course_id": course_id,
        "message": "Explain Newton's second law and the formula for force"
    }
    response = client.post("/api/tutor/chat", json=chat_payload)
    assert response.status_code == 200

    data = response.json()
    assert data["grounded"] is True
    assert "Newton's second law" in data["answer"]
    assert len(data["sources"]) > 0

    # 3. Verify exact page citation
    first_citation = data["sources"][0]
    assert first_citation["source_id"] == source_id
    assert first_citation["file_name"] == "newton_laws.pdf"
    assert first_citation["page"] == 2  # Second law is on page 2!
    assert len(first_citation["excerpt"]) > 0
    assert "F = m" in first_citation["excerpt"] or "acceleration" in first_citation["excerpt"] or "force" in first_citation["excerpt"].lower()

def test_tutor_unrelated_question_grounding_rejection(client, sample_physics_pdf):
    """
    Test grounding rejection:
    If a student asks a question unrelated to the uploaded material,
    grounded must be false and no fake citations returned.
    """
    # 1. Create course and upload physics document
    c_res = client.post("/api/courses", json={"title": "Physics 101"})
    course_id = c_res.json()["id"]

    files = {"file": ("newton_laws.pdf", io.BytesIO(sample_physics_pdf), "application/pdf")}
    client.post(f"/api/courses/{course_id}/upload", files=files)

    # Inject mock refusal response for off-material query
    mock_refusal_llm = MockLLMService(
        response_text="I couldn't find enough information about this topic in the uploaded course material."
    )
    tutor_service._llm_service = mock_refusal_llm

    # 2. Ask completely unrelated question (e.g., Photosynthesis in plants)
    chat_payload = {
        "course_id": course_id,
        "message": "How does chlorophyll absorb light during plant photosynthesis?"
    }
    response = client.post("/api/tutor/chat", json=chat_payload)
    assert response.status_code == 200

    data = response.json()
    assert data["grounded"] is False
    assert data["sources"] == []
    assert "couldn't find enough information" in data["answer"]
    tutor_service._llm_service = None

def test_tutor_course_isolation(client, sample_physics_pdf):
    """
    The retrieval system must NEVER mix material from another course.
    """
    # Course A: has physics
    c_a_res = client.post("/api/courses", json={"title": "Physics Course"})
    course_a_id = c_a_res.json()["id"]
    files = {"file": ("newton_laws.pdf", io.BytesIO(sample_physics_pdf), "application/pdf")}
    client.post(f"/api/courses/{course_a_id}/upload", files=files)

    # Course B: empty course
    c_b_res = client.post("/api/courses", json={"title": "Literature Course"})
    course_b_id = c_b_res.json()["id"]

    # Querying Course B for Newton's laws must NOT retrieve Course A's material!
    chat_payload = {
        "course_id": course_b_id,
        "message": "Explain Newton's second law"
    }
    response = client.post("/api/tutor/chat", json=chat_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["grounded"] is False
    assert data["sources"] == []

def test_tutor_course_not_found(client):
    """Querying a non-existent course returns 404."""
    chat_payload = {
        "course_id": "non-existent-course-id",
        "message": "What is force?"
    }
    response = client.post("/api/tutor/chat", json=chat_payload)
    assert response.status_code == 404

def test_tutor_empty_question(client):
    """Empty question returns 422 validation error."""
    create_res = client.post("/api/courses", json={"title": "Physics"})
    course_id = create_res.json()["id"]

    chat_payload = {
        "course_id": course_id,
        "message": ""
    }
    response = client.post("/api/tutor/chat", json=chat_payload)
    assert response.status_code == 422
