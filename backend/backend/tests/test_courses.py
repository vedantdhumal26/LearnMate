import pytest

def test_create_course(client):
    """Test successful course creation."""
    payload = {
        "title": "Engineering Physics",
        "description": "Physics course material for undergraduate students"
    }
    response = client.post("/api/courses", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["title"] == payload["title"]
    assert data["description"] == payload["description"]
    assert "created_at" in data

def test_create_course_validation(client):
    """Test validation when creating course with empty title."""
    response = client.post("/api/courses", json={"title": ""})
    assert response.status_code == 422

def test_list_courses(client):
    """Test listing all courses."""
    client.post("/api/courses", json={"title": "Course 1", "description": "Desc 1"})
    client.post("/api/courses", json={"title": "Course 2", "description": "Desc 2"})

    response = client.get("/api/courses")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2
    titles = [c["title"] for c in data]
    assert "Course 1" in titles
    assert "Course 2" in titles

def test_get_course_details(client):
    """Test retrieving course by ID with detail fields."""
    create_res = client.post("/api/courses", json={"title": "Quantum Mechanics"})
    course_id = create_res.json()["id"]

    response = client.get(f"/api/courses/{course_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == course_id
    assert data["title"] == "Quantum Mechanics"
    assert data["chunk_count"] == 0
    assert isinstance(data["sources"], list)

def test_get_nonexistent_course(client):
    """Test getting course that does not exist returns 404."""
    response = client.get("/api/courses/non-existent-uuid")
    assert response.status_code == 404

def test_rename_course(client):
    """Test renaming an existing course."""
    create_res = client.post("/api/courses", json={"title": "Thermodynamics"})
    course_id = create_res.json()["id"]

    patch_res = client.patch(f"/api/courses/{course_id}", json={"title": "Applied Thermodynamics"})
    assert patch_res.status_code == 200
    assert patch_res.json()["title"] == "Applied Thermodynamics"

    get_res = client.get(f"/api/courses/{course_id}")
    assert get_res.json()["title"] == "Applied Thermodynamics"

def test_delete_course(client):
    """Test deleting an owned course."""
    create_res = client.post("/api/courses", json={"title": "Temporary Course"})
    course_id = create_res.json()["id"]

    del_res = client.delete(f"/api/courses/{course_id}")
    assert del_res.status_code == 204

    get_res = client.get(f"/api/courses/{course_id}")
    assert get_res.status_code == 404
