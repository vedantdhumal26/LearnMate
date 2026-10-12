import io
from app.models.document_chunk import DocumentChunk
from app.models.source import Source

def test_upload_invalid_extension(client):
    """Reject non-PDF file uploads."""
    create_res = client.post("/api/courses", json={"title": "Test Course"})
    course_id = create_res.json()["id"]

    files = {"file": ("test.txt", io.BytesIO(b"Hello world"), "text/plain")}
    response = client.post(f"/api/courses/{course_id}/upload", files=files)
    assert response.status_code == 400
    assert "Only .pdf files are supported" in response.json()["detail"]

def test_upload_empty_pdf(client):
    """Reject empty PDF files."""
    create_res = client.post("/api/courses", json={"title": "Test Course"})
    course_id = create_res.json()["id"]

    files = {"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")}
    response = client.post(f"/api/courses/{course_id}/upload", files=files)
    assert response.status_code == 400
    assert "empty" in response.json()["detail"]

def test_upload_corrupt_pdf_header(client):
    """Reject files with .pdf extension that lack %PDF- header."""
    create_res = client.post("/api/courses", json={"title": "Test Course"})
    course_id = create_res.json()["id"]

    files = {"file": ("corrupt.pdf", io.BytesIO(b"Not a real PDF content"), "application/pdf")}
    response = client.post(f"/api/courses/{course_id}/upload", files=files)
    assert response.status_code == 400
    assert "standard PDF header" in response.json()["detail"]

def test_upload_pdf_course_not_found(client, sample_physics_pdf):
    """Uploading to a non-existent course returns 404."""
    files = {"file": ("physics.pdf", io.BytesIO(sample_physics_pdf), "application/pdf")}
    response = client.post("/api/courses/non-existent-course-id/upload", files=files)
    assert response.status_code == 404

def test_upload_and_process_pdf_complete(client, db_session, sample_physics_pdf):
    """
    Test end-to-end PDF upload:
    - PDF processing
    - Text extraction
    - Page metadata preservation
    - Chunk creation
    - Embeddings & Qdrant vector storage
    """
    # 1. Create course
    create_res = client.post("/api/courses", json={"title": "Classical Mechanics"})
    course_id = create_res.json()["id"]

    # 2. Upload valid 2-page physics PDF
    files = {"file": ("physics_mechanics.pdf", io.BytesIO(sample_physics_pdf), "application/pdf")}
    response = client.post(f"/api/courses/{course_id}/upload", files=files)
    assert response.status_code == 201

    data = response.json()
    assert "source_id" in data
    assert data["file_name"] == "physics_mechanics.pdf"
    assert data["status"] == "completed"

    source_id = data["source_id"]

    # 3. Verify PostgreSQL Source record
    source = db_session.query(Source).filter(Source.id == source_id).first()
    assert source is not None
    assert source.processing_status == "completed"
    assert source.file_name == "physics_mechanics.pdf"

    # 4. Verify DocumentChunk records in PostgreSQL
    chunks = db_session.query(DocumentChunk).filter(DocumentChunk.source_id == source_id).all()
    assert len(chunks) >= 2  # At least 2 chunks across the 2 pages

    # 5. Verify page numbers are strictly preserved (1 and 2)
    page_numbers = {c.page_number for c in chunks}
    assert 1 in page_numbers
    assert 2 in page_numbers

    # 6. Verify chunk contents and deterministic hashes
    for chunk in chunks:
        assert chunk.course_id == course_id
        assert chunk.content_hash is not None
        assert len(chunk.content_hash) == 64
        assert len(chunk.content) > 0

    # Page 1 must mention inertia / First Law
    page1_chunks = [c for c in chunks if c.page_number == 1]
    assert any("First Law" in c.content or "inertia" in c.content for c in page1_chunks)

    # Page 2 must mention F = m * a / Second Law
    page2_chunks = [c for c in chunks if c.page_number == 2]
    assert any("Second Law" in c.content or "F = m" in c.content for c in page2_chunks)

    # 7. Verify duplicate upload is rejected with 409 Conflict
    files_dup = {"file": ("physics_mechanics.pdf", io.BytesIO(sample_physics_pdf), "application/pdf")}
    dup_res = client.post(f"/api/courses/{course_id}/upload", files=files_dup)
    assert dup_res.status_code == 409

def test_delete_uploaded_material(client, sample_physics_pdf):
    """Test deleting an uploaded material."""
    create_res = client.post("/api/courses", json={"title": "Delete Material Course"})
    course_id = create_res.json()["id"]

    files = {"file": ("delete_me.pdf", io.BytesIO(sample_physics_pdf), "application/pdf")}
    up_res = client.post(f"/api/courses/{course_id}/upload", files=files)
    assert up_res.status_code == 201
    source_id = up_res.json()["source_id"]

    del_res = client.delete(f"/api/courses/{course_id}/materials/{source_id}")
    assert del_res.status_code == 204

    # Status check should return 404
    status_res = client.get(f"/api/courses/{course_id}/uploads/{source_id}")
    assert status_res.status_code == 404
