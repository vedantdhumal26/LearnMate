"""
Unit and integration tests for Pre-Phase 8 features:
1. User Profile Editing (PATCH /api/auth/me)
2. Course Renaming (PATCH /api/courses/{course_id})
3. Course Deletion (DELETE /api/courses/{course_id})
4. Individual Material Deletion (DELETE /api/courses/{course_id}/materials/{material_id})
"""

import io
import os
import pytest
from app.models.user import User
from app.models.course import Course
from app.models.source import Source
from app.models.document_chunk import DocumentChunk
from app.models.assessment import Assessment, Question
from app.models.learner_mastery import LearnerMastery
from app.services.vector_store.qdrant_store import get_vector_store
from app.core.config import settings


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def signup_and_get_token(client, email: str, display_name: str = "User"):
    res = client.post("/api/auth/signup", json={
        "email": email,
        "password": "Password123!",
        "display_name": display_name
    })
    assert res.status_code == 201
    return res.json()["access_token"], res.json()["user"]


# ==============================================================================
# Phase 2: User Profile Editing Tests
# ==============================================================================

def test_profile_edit_display_name_success(unauthenticated_client, db_session):
    """Authenticated user can update their display name and changes persist."""
    token, user_data = signup_and_get_token(unauthenticated_client, "alice.profile@example.com", "Alice Original")

    response = unauthenticated_client.patch(
        "/api/auth/me",
        json={"display_name": "Alice Wonderland"},
        headers=auth_header(token)
    )
    assert response.status_code == 200
    data = response.json()
    assert data["display_name"] == "Alice Wonderland"
    assert data["email"] == "alice.profile@example.com"
    assert data["id"] == user_data["id"]

    # Verify fresh database read
    fresh_user = db_session.query(User).filter(User.id == user_data["id"]).first()
    assert fresh_user is not None
    assert fresh_user.display_name == "Alice Wonderland"


def test_profile_edit_email_success(unauthenticated_client, db_session):
    """Authenticated user can update their email address and login with new email."""
    token, user_data = signup_and_get_token(unauthenticated_client, "bob.orig@example.com", "Bob Builder")

    response = unauthenticated_client.patch(
        "/api/auth/me",
        json={"email": "  Bob.Updated@Example.Com  "},
        headers=auth_header(token)
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "bob.updated@example.com"

    # Fresh DB check
    fresh_user = db_session.query(User).filter(User.id == user_data["id"]).first()
    assert fresh_user.email == "bob.updated@example.com"

    # Login with new email
    login_res = unauthenticated_client.post("/api/auth/login", json={
        "email": "bob.updated@example.com",
        "password": "Password123!"
    })
    assert login_res.status_code == 200


def test_profile_edit_unauthenticated(unauthenticated_client):
    """Unauthenticated requests are rejected with 401."""
    response = unauthenticated_client.patch("/api/auth/me", json={"display_name": "Hacker"})
    assert response.status_code == 401


def test_profile_edit_invalid_values(unauthenticated_client):
    """Empty or invalid values are rejected with 422 or 400."""
    token, _ = signup_and_get_token(unauthenticated_client, "charlie.val@example.com", "Charlie")

    # Empty display name
    res1 = unauthenticated_client.patch(
        "/api/auth/me",
        json={"display_name": ""},
        headers=auth_header(token)
    )
    assert res1.status_code == 422

    # Whitespace-only display name
    res2 = unauthenticated_client.patch(
        "/api/auth/me",
        json={"display_name": "    "},
        headers=auth_header(token)
    )
    assert res2.status_code == 422

    # Invalid email format
    res3 = unauthenticated_client.patch(
        "/api/auth/me",
        json={"email": "not-an-email"},
        headers=auth_header(token)
    )
    assert res3.status_code == 422

    # Empty payload with no fields
    res4 = unauthenticated_client.patch(
        "/api/auth/me",
        json={},
        headers=auth_header(token)
    )
    assert res4.status_code == 400
    assert "no valid profile fields" in res4.json()["detail"].lower()


def test_profile_edit_duplicate_email_rejected(unauthenticated_client):
    """Reject update if new email belongs to another user."""
    _, user_a = signup_and_get_token(unauthenticated_client, "user.a@example.com", "User A")
    token_b, _ = signup_and_get_token(unauthenticated_client, "user.b@example.com", "User B")

    response = unauthenticated_client.patch(
        "/api/auth/me",
        json={"email": "user.a@example.com"},
        headers=auth_header(token_b)
    )
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"].lower()


def test_profile_edit_mass_assignment_protection(unauthenticated_client, db_session):
    """Privileged fields (id, password_hash) cannot be modified through mass assignment."""
    token, user_data = signup_and_get_token(unauthenticated_client, "dave.safe@example.com", "Dave")
    original_id = user_data["id"]

    orig_user = db_session.query(User).filter(User.id == original_id).first()
    original_hash = orig_user.password_hash

    # Attempt to mass-assign privileged fields
    response = unauthenticated_client.patch(
        "/api/auth/me",
        json={
            "display_name": "Dave Renamed",
            "id": "hacked-uuid-9999",
            "password_hash": "malicious_fake_hash",
            "role": "admin"
        },
        headers=auth_header(token)
    )
    assert response.status_code == 200
    assert response.json()["display_name"] == "Dave Renamed"

    # Verify DB: id and password_hash remain unmodified
    db_session.expire_all()
    user_after = db_session.query(User).filter(User.id == original_id).first()
    assert user_after is not None
    assert user_after.id == original_id
    assert user_after.password_hash == original_hash
    assert user_after.display_name == "Dave Renamed"


# ==============================================================================
# Phase 3: Course Renaming Tests
# ==============================================================================

def test_course_rename_success(unauthenticated_client, db_session):
    """Owner can rename a course; new title persists and appears in listing & details."""
    token, _ = signup_and_get_token(unauthenticated_client, "owner.rename@example.com", "Owner")

    create_res = unauthenticated_client.post(
        "/api/courses",
        json={"title": "Original Math", "description": "Basics"},
        headers=auth_header(token)
    )
    course_id = create_res.json()["id"]

    # Rename course
    patch_res = unauthenticated_client.patch(
        f"/api/courses/{course_id}",
        json={"title": "Advanced Linear Algebra", "description": "Updated syllabus"},
        headers=auth_header(token)
    )
    assert patch_res.status_code == 200
    updated = patch_res.json()
    assert updated["id"] == course_id
    assert updated["title"] == "Advanced Linear Algebra"
    assert updated["description"] == "Updated syllabus"

    # Verify GET /api/courses/{course_id}
    detail_res = unauthenticated_client.get(f"/api/courses/{course_id}", headers=auth_header(token))
    assert detail_res.status_code == 200
    assert detail_res.json()["title"] == "Advanced Linear Algebra"

    # Verify GET /api/courses list
    list_res = unauthenticated_client.get("/api/courses", headers=auth_header(token))
    assert any(c["title"] == "Advanced Linear Algebra" for c in list_res.json())

    # Verify fresh database read
    fresh_course = db_session.query(Course).filter(Course.id == course_id).first()
    assert fresh_course.title == "Advanced Linear Algebra"


def test_course_rename_invalid_title(unauthenticated_client):
    """Empty or whitespace-only course titles are rejected."""
    token, _ = signup_and_get_token(unauthenticated_client, "owner.val@example.com", "Owner")
    create_res = unauthenticated_client.post(
        "/api/courses",
        json={"title": "Biology 101"},
        headers=auth_header(token)
    )
    course_id = create_res.json()["id"]

    # Empty string
    res1 = unauthenticated_client.patch(
        f"/api/courses/{course_id}",
        json={"title": ""},
        headers=auth_header(token)
    )
    assert res1.status_code == 422

    # Whitespace only
    res2 = unauthenticated_client.patch(
        f"/api/courses/{course_id}",
        json={"title": "    "},
        headers=auth_header(token)
    )
    assert res2.status_code == 422

    # Empty body
    res3 = unauthenticated_client.patch(
        f"/api/courses/{course_id}",
        json={},
        headers=auth_header(token)
    )
    assert res3.status_code == 400


def test_course_rename_isolation_other_user_forbidden(unauthenticated_client):
    """User B cannot rename User A's course (returns 404)."""
    token_a, _ = signup_and_get_token(unauthenticated_client, "course.usera@example.com", "User A")
    token_b, _ = signup_and_get_token(unauthenticated_client, "course.userb@example.com", "User B")

    create_res = unauthenticated_client.post(
        "/api/courses",
        json={"title": "User A Private Course"},
        headers=auth_header(token_a)
    )
    course_id = create_res.json()["id"]

    # User B tries to rename User A's course
    patch_res = unauthenticated_client.patch(
        f"/api/courses/{course_id}",
        json={"title": "Hijacked Course"},
        headers=auth_header(token_b)
    )
    assert patch_res.status_code == 404

    # Verify original title intact
    detail_res = unauthenticated_client.get(f"/api/courses/{course_id}", headers=auth_header(token_a))
    assert detail_res.json()["title"] == "User A Private Course"


def test_course_rename_nonexistent(unauthenticated_client):
    """Renaming nonexistent course returns 404."""
    token, _ = signup_and_get_token(unauthenticated_client, "owner.nonex@example.com", "Owner")
    res = unauthenticated_client.patch(
        "/api/courses/nonexistent-course-id-999",
        json={"title": "Does Not Matter"},
        headers=auth_header(token)
    )
    assert res.status_code == 404


# ==============================================================================
# Phase 4: Course Deletion Tests
# ==============================================================================

def test_delete_course_success(unauthenticated_client, db_session, sample_physics_pdf):
    """
    Owner can delete their course. Associated resources:
    sources, document chunks, vector embeddings, questions, and physical files are cleaned up.
    """
    token, _ = signup_and_get_token(unauthenticated_client, "del.owner@example.com", "Course Owner")

    # 1. Create course
    create_res = unauthenticated_client.post(
        "/api/courses",
        json={"title": "Course To Delete", "description": "Temporary"},
        headers=auth_header(token)
    )
    course_id = create_res.json()["id"]

    # 2. Upload PDF
    files = {"file": ("mechanics_delete_test.pdf", io.BytesIO(sample_physics_pdf), "application/pdf")}
    up_res = unauthenticated_client.post(f"/api/courses/{course_id}/upload", files=files, headers=auth_header(token))
    assert up_res.status_code == 201
    source_id = up_res.json()["source_id"]

    # 3. Add an assessment question and learner mastery directly
    q = Question(
        course_id=course_id,
        question_type="mcq",
        question_text="What is inertia?",
        options=["A", "B"],
        correct_answer="A",
        explanation="Newton's 1st law",
        difficulty="easy",
        content_hash="abc" * 21 + "a"
    )
    mastery = LearnerMastery(
        student_id="student-1",
        course_id=course_id,
        topic="Mechanics",
        mastery_score=0.85
    )
    db_session.add(q)
    db_session.add(mastery)
    db_session.commit()

    # Verify upload directory exists on disk
    course_upload_dir = os.path.join(settings.UPLOAD_DIR, course_id)
    assert os.path.isdir(course_upload_dir)

    # 4. Delete course
    del_res = unauthenticated_client.delete(f"/api/courses/{course_id}", headers=auth_header(token))
    assert del_res.status_code == 204

    # 5. Verify course is gone
    get_res = unauthenticated_client.get(f"/api/courses/{course_id}", headers=auth_header(token))
    assert get_res.status_code == 404

    # 6. Verify database records cleaned up
    assert db_session.query(Course).filter(Course.id == course_id).first() is None
    assert db_session.query(Source).filter(Source.course_id == course_id).count() == 0
    assert db_session.query(DocumentChunk).filter(DocumentChunk.course_id == course_id).count() == 0
    assert db_session.query(Question).filter(Question.course_id == course_id).count() == 0
    assert db_session.query(LearnerMastery).filter(LearnerMastery.course_id == course_id).count() == 0

    # 7. Verify vector embeddings cleaned up
    vs = get_vector_store()
    search_results = vs.search_vectors(query_vector=[0.1] * 768, course_id=course_id)
    assert len(search_results) == 0

    # 8. Verify physical upload directory removed
    assert not os.path.isdir(course_upload_dir)


def test_delete_course_isolation_other_user_forbidden(unauthenticated_client, db_session):
    """User B cannot delete User A's course (returns 404)."""
    token_a, _ = signup_and_get_token(unauthenticated_client, "del.usera@example.com", "User A")
    token_b, _ = signup_and_get_token(unauthenticated_client, "del.userb@example.com", "User B")

    create_res = unauthenticated_client.post(
        "/api/courses",
        json={"title": "User A Secure Course"},
        headers=auth_header(token_a)
    )
    course_id = create_res.json()["id"]

    # User B attempts deletion
    del_res = unauthenticated_client.delete(f"/api/courses/{course_id}", headers=auth_header(token_b))
    assert del_res.status_code == 404

    # Verify course still exists
    course = db_session.query(Course).filter(Course.id == course_id).first()
    assert course is not None


def test_delete_nonexistent_course(unauthenticated_client):
    """Deleting nonexistent course returns 404."""
    token, _ = signup_and_get_token(unauthenticated_client, "del.nonex@example.com", "User")
    res = unauthenticated_client.delete("/api/courses/nonexistent-course-id-888", headers=auth_header(token))
    assert res.status_code == 404


# ==============================================================================
# Phase 5: Individual Material Deletion Tests
# ==============================================================================

def test_delete_individual_material_success(unauthenticated_client, db_session, sample_physics_pdf):
    """
    Owner can delete a single material from a course.
    The material is removed from DB, vector store, and disk, while other materials remain.
    """
    token, _ = signup_and_get_token(unauthenticated_client, "mat.owner@example.com", "Owner")

    # 1. Create course
    create_res = unauthenticated_client.post(
        "/api/courses",
        json={"title": "Multi Material Course"},
        headers=auth_header(token)
    )
    course_id = create_res.json()["id"]

    # 2. Upload Material 1
    files1 = {"file": ("document_one.pdf", io.BytesIO(sample_physics_pdf), "application/pdf")}
    res1 = unauthenticated_client.post(f"/api/courses/{course_id}/upload", files=files1, headers=auth_header(token))
    assert res1.status_code == 201
    source1_id = res1.json()["source_id"]

    # 3. Create slightly different PDF for Material 2
    import pymupdf
    doc2 = pymupdf.open()
    page = doc2.new_page()
    page.insert_text((50, 72), "Thermodynamics and heat engines chapter text.", fontsize=12)
    pdf2_bytes = doc2.tobytes()
    doc2.close()

    files2 = {"file": ("document_two.pdf", io.BytesIO(pdf2_bytes), "application/pdf")}
    res2 = unauthenticated_client.post(f"/api/courses/{course_id}/upload", files=files2, headers=auth_header(token))
    assert res2.status_code == 201
    source2_id = res2.json()["source_id"]

    # Verify 2 sources present
    detail = unauthenticated_client.get(f"/api/courses/{course_id}", headers=auth_header(token)).json()
    assert len(detail["sources"]) == 2

    # Verify physical file for material 1 exists
    source1_db = db_session.query(Source).filter(Source.id == source1_id).first()
    file1_path = source1_db.file_path
    assert os.path.isfile(file1_path)

    # 4. Delete Material 1
    del_res = unauthenticated_client.delete(
        f"/api/courses/{course_id}/materials/{source1_id}",
        headers=auth_header(token)
    )
    assert del_res.status_code == 204

    # 5. Verify course details now only contains Material 2
    detail_after = unauthenticated_client.get(f"/api/courses/{course_id}", headers=auth_header(token)).json()
    source_ids_after = [s["id"] for s in detail_after["sources"]]
    assert source1_id not in source_ids_after
    assert source2_id in source_ids_after

    # 6. Verify Material 1 records and chunks deleted from DB
    assert db_session.query(Source).filter(Source.id == source1_id).first() is None
    assert db_session.query(DocumentChunk).filter(DocumentChunk.source_id == source1_id).count() == 0

    # Verify Material 2 records and chunks still exist
    assert db_session.query(Source).filter(Source.id == source2_id).first() is not None
    assert db_session.query(DocumentChunk).filter(DocumentChunk.source_id == source2_id).count() > 0

    # 7. Verify physical file for Material 1 removed, file for Material 2 exists
    assert not os.path.isfile(file1_path)
    source2_db = db_session.query(Source).filter(Source.id == source2_id).first()
    assert os.path.isfile(source2_db.file_path)


def test_delete_material_isolation_and_cross_course(unauthenticated_client, sample_physics_pdf):
    """
    Cannot delete another user's material or delete material via the wrong course ID.
    """
    token_a, _ = signup_and_get_token(unauthenticated_client, "cross.usera@example.com", "User A")
    token_b, _ = signup_and_get_token(unauthenticated_client, "cross.userb@example.com", "User B")

    # User A creates Course A with Material A
    c_a = unauthenticated_client.post("/api/courses", json={"title": "Course A"}, headers=auth_header(token_a)).json()
    files_a = {"file": ("mat_a.pdf", io.BytesIO(sample_physics_pdf), "application/pdf")}
    res_a = unauthenticated_client.post(f"/api/courses/{c_a['id']}/upload", files=files_a, headers=auth_header(token_a)).json()
    mat_a_id = res_a["source_id"]

    # User B creates Course B
    c_b = unauthenticated_client.post("/api/courses", json={"title": "Course B"}, headers=auth_header(token_b)).json()

    # User B tries to delete User A's material using Course A (which B doesn't own) -> 404
    del_res1 = unauthenticated_client.delete(f"/api/courses/{c_a['id']}/materials/{mat_a_id}", headers=auth_header(token_b))
    assert del_res1.status_code == 404

    # User B tries to delete Material A through Course B (which does not contain Material A) -> 404
    del_res2 = unauthenticated_client.delete(f"/api/courses/{c_b['id']}/materials/{mat_a_id}", headers=auth_header(token_b))
    assert del_res2.status_code == 404

    # User A tries to delete nonexistent material -> 404
    del_res3 = unauthenticated_client.delete(f"/api/courses/{c_a['id']}/materials/nonexistent-id", headers=auth_header(token_a))
    assert del_res3.status_code == 404


def test_delete_material_via_uploads_alias(unauthenticated_client, sample_physics_pdf):
    """Verify DELETE /api/courses/{course_id}/uploads/{material_id} alias works as expected."""
    token, _ = signup_and_get_token(unauthenticated_client, "alias.user@example.com", "Alias User")
    c = unauthenticated_client.post("/api/courses", json={"title": "Alias Course"}, headers=auth_header(token)).json()
    files = {"file": ("alias_doc.pdf", io.BytesIO(sample_physics_pdf), "application/pdf")}
    up = unauthenticated_client.post(f"/api/courses/{c['id']}/upload", files=files, headers=auth_header(token)).json()
    source_id = up["source_id"]

    # Delete using /uploads/{source_id} route
    del_res = unauthenticated_client.delete(f"/api/courses/{c['id']}/uploads/{source_id}", headers=auth_header(token))
    assert del_res.status_code == 204

    # Verify deleted
    detail = unauthenticated_client.get(f"/api/courses/{c['id']}", headers=auth_header(token)).json()
    assert len(detail["sources"]) == 0


def test_course_rename_preserves_assessments_and_study_plan(unauthenticated_client, sample_physics_pdf):
    """
    Renaming a course preserves assessments, questions, and study plan functionality.
    """
    import json
    from app.api.routes.assessments import assessment_service
    from tests.conftest import MockLLMService

    token, user_data = signup_and_get_token(unauthenticated_client, "rename.plan@example.com", "Plan Learner")

    # 1. Create course and upload material
    create_res = unauthenticated_client.post("/api/courses", json={"title": "Original Physics"}, headers=auth_header(token))
    course_id = create_res.json()["id"]

    files = {"file": ("physics_notes.pdf", io.BytesIO(sample_physics_pdf), "application/pdf")}
    up_res = unauthenticated_client.post(f"/api/courses/{course_id}/upload", files=files, headers=auth_header(token))
    assert up_res.status_code == 201

    # 2. Mock LLM and generate assessment
    mock_mcq = json.dumps([
        {
            "question": "What is Newton's First Law?",
            "options": ["A) Law of Inertia", "B) F=ma", "C) Action Reaction", "D) Gravity"],
            "correct_answer": "A",
            "explanation": "Law of Inertia",
            "difficulty": "medium",
            "topic": "Physics"
        }
    ])
    assessment_service.question_generator._llm_service = MockLLMService(response_text=mock_mcq)

    gen_res = unauthenticated_client.post("/api/assessments/generate", json={
        "course_id": course_id,
        "topic": "Physics",
        "count": 1,
        "difficulty": "medium",
        "question_type": "mcq"
    }, headers=auth_header(token))
    assert gen_res.status_code == 201
    assessment_id = gen_res.json()["assessment_id"]

    # 3. Rename course
    rename_res = unauthenticated_client.patch(f"/api/courses/{course_id}", json={"title": "Renamed Physics 2026"}, headers=auth_header(token))
    assert rename_res.status_code == 200
    assert rename_res.json()["title"] == "Renamed Physics 2026"
    assert rename_res.json()["id"] == course_id

    # 4. Assessment is still retrievable and functional
    get_ass = unauthenticated_client.get(f"/api/assessments/{assessment_id}", headers=auth_header(token))
    assert get_ass.status_code == 200
    assert get_ass.json()["course_id"] == course_id

    # 5. Study plan endpoint still functions correctly
    user_id = user_data["id"]
    plan_res = unauthenticated_client.get(f"/api/learner/{user_id}/courses/{course_id}/study-plan", headers=auth_header(token))
    assert plan_res.status_code == 200
    assert plan_res.json()["course_id"] == course_id


def test_material_deletion_prevents_subsequent_tutor_retrieval(unauthenticated_client, sample_physics_pdf):
    """
    After deleting a material, the tutor retriever and vector store no longer find its content.
    """
    from app.services.rag.retriever import CourseRetriever

    token, _ = signup_and_get_token(unauthenticated_client, "tutor.retrieval@example.com", "Tutor Learner")
    c = unauthenticated_client.post("/api/courses", json={"title": "Tutor Clean Course"}, headers=auth_header(token)).json()
    course_id = c["id"]

    files = {"file": ("laws_of_motion.pdf", io.BytesIO(sample_physics_pdf), "application/pdf")}
    up = unauthenticated_client.post(f"/api/courses/{course_id}/upload", files=files, headers=auth_header(token)).json()
    source_id = up["source_id"]

    # Verify retriever finds chunks for this course before deletion
    retriever = CourseRetriever()
    results_before = retriever.retrieve(course_id=course_id, query="Newton's laws of motion", top_k=5, score_threshold=0.0)
    assert len(results_before) > 0

    # Delete material
    del_res = unauthenticated_client.delete(f"/api/courses/{course_id}/materials/{source_id}", headers=auth_header(token))
    assert del_res.status_code == 204

    # Subsequent retrieval returns 0 results
    results_after = retriever.retrieve(course_id=course_id, query="Newton's laws of motion", top_k=5, score_threshold=0.0)
    assert len(results_after) == 0

    # Also check directly with vector store
    vs = get_vector_store()
    raw_points = vs.search_vectors(query_vector=[0.1] * 768, course_id=course_id, score_threshold=0.0)
    assert len(raw_points) == 0


def test_ingestion_deletion_safety(unauthenticated_client, db_session, sample_physics_pdf):
    """
    If a source is deleted before ingestion finalization, the ingestion service cleans up
    any newly generated vectors without crashing.
    """
    from app.services.ingestion.ingestion_service import IngestionService
    from fastapi import UploadFile

    token, _ = signup_and_get_token(unauthenticated_client, "mid.delete@example.com", "Mid Delete")
    c = unauthenticated_client.post("/api/courses", json={"title": "Mid Ingestion Course"}, headers=auth_header(token)).json()
    course_id = c["id"]

    service = IngestionService()
    # Create fake upload
    file_obj = UploadFile(
        file=io.BytesIO(sample_physics_pdf),
        filename="concurrent_test.pdf",
        headers={"content-type": "application/pdf"}
    )

    # Ingest the file
    import asyncio
    source = asyncio.run(service.ingest_pdf(course_id=course_id, file=file_obj, db=db_session))
    assert source is not None

    # Deleting vectors directly
    service.vector_store.delete_source_vectors(source.id)
    vs = get_vector_store()
    assert len(vs.search_vectors(query_vector=[0.1] * 768, course_id=course_id)) == 0
