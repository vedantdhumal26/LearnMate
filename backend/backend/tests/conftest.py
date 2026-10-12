import pytest
import os
import shutil
import tempfile
import pymupdf
from typing import Generator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Setup test directories before importing app so Qdrant client uses isolated test directory
_test_upload_dir = tempfile.mkdtemp()
_test_qdrant_dir = tempfile.mkdtemp()
os.environ["UPLOAD_DIR"] = _test_upload_dir
os.environ["QDRANT_STORAGE_PATH"] = _test_qdrant_dir

from app.core.config import settings
settings.UPLOAD_DIR = _test_upload_dir
settings.QDRANT_STORAGE_PATH = _test_qdrant_dir
if not settings.LLM_API_KEY:
    settings.LLM_API_KEY = "mock-test-key"


from app.core.database import Base, get_db
from app.main import app
from app.services.vector_store.qdrant_store import QdrantVectorStore
from app.services.llm.llm_service import LLMService

# Test SQLite in-memory engine
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

@pytest.fixture(scope="session", autouse=True)
def setup_test_directories():
    yield
    shutil.rmtree(_test_upload_dir, ignore_errors=True)
    shutil.rmtree(_test_qdrant_dir, ignore_errors=True)

@pytest.fixture(scope="function")
def db_session() -> Generator:
    """Create fresh tables for every test function."""
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)

from app.models.user import User
from app.models.course import DEMO_USER_ID, DEMO_USER_EMAIL
from app.utils.password import hash_password
from app.core.jwt import create_access_token

@pytest.fixture(scope="function")
def default_user(db_session) -> User:
    """Ensure a default test user exists in the session."""
    user = db_session.query(User).filter(User.id == DEMO_USER_ID).first()
    if not user:
        user = User(
            id=DEMO_USER_ID,
            email=DEMO_USER_EMAIL,
            password_hash=hash_password("DemoPassword123!"),
            display_name="Demo Learner"
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
    return user

@pytest.fixture(scope="function")
def client(db_session, default_user) -> Generator[TestClient, None, None]:
    """TestClient that overrides get_db dependency and sets default Bearer auth header."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    token = create_access_token(user_id=default_user.id)
    with TestClient(app) as test_client:
        test_client.headers["Authorization"] = f"Bearer {token}"
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture(scope="function")
def unauthenticated_client(db_session) -> Generator[TestClient, None, None]:
    """TestClient that overrides get_db dependency but has no Authorization header."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture
def sample_physics_pdf() -> bytes:
    """Generate a real 2-page PDF document on physics using PyMuPDF."""
    doc = pymupdf.open()
    
    # Page 1 (Page number 1)
    page1 = doc.new_page()
    page1_text = (
        "Chapter 1: Newton's First Law of Motion\n\n"
        "An object at rest stays at rest and an object in motion stays in motion "
        "with the same speed and in the same direction unless acted upon by an unbalanced force. "
        "This principle is also universally known as the law of inertia."
    )
    page1.insert_text((50, 72), page1_text, fontsize=12)

    # Page 2 (Page number 2)
    page2 = doc.new_page()
    page2_text = (
        "Chapter 2: Newton's Second Law of Motion\n\n"
        "The acceleration of an object as produced by a net force is directly proportional "
        "to the magnitude of the net force, in the same direction as the net force, "
        "and inversely proportional to the mass of the object. Mathematically, F = m * a. "
        "Force is measured in Newtons, mass in kilograms, and acceleration in meters per second squared."
    )
    page2.insert_text((50, 72), page2_text, fontsize=12)

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes

class MockLLMService(LLMService):
    def __init__(self, response_text: str = "According to Newton's Second Law, Force equals mass times acceleration (F = ma)."):
        self.response_text = response_text

    def generate(self, prompt: str, system_prompt: str = None, *args, **kwargs) -> str:
        return self.response_text
