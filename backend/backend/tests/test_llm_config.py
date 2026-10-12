import pytest
import io
from unittest.mock import patch
from fastapi import HTTPException

from app.core.config import Settings, _BACKEND_DIR, _ENV_FILES
from app.services.llm.llm_service import OpenAILLMService, get_llm_service
from app.api.routes.tutor import tutor_service


def test_openai_missing_api_key_raises_configuration_error(monkeypatch):
    """
    Verify that initializing OpenAILLMService for provider 'openai'
    without an API key raises the expected configuration ValueError.
    No network or external API call should be made.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    with patch("app.services.llm.llm_service.settings.LLM_API_KEY", None):
        with pytest.raises(ValueError) as exc_info:
            OpenAILLMService(provider="openai", api_key=None)

        err_msg = str(exc_info.value)
        assert "LLM_API_KEY is required for provider 'openai'" in err_msg
        assert "Please set LLM_API_KEY in your .env file or environment variables" in err_msg


def test_groq_missing_api_key_raises_configuration_error(monkeypatch):
    """
    Verify that initializing OpenAILLMService for provider 'groq'
    without an API key raises the expected configuration ValueError.
    No network or external API call should be made.
    """
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    with patch("app.services.llm.llm_service.settings.LLM_API_KEY", None):
        with pytest.raises(ValueError) as exc_info:
            OpenAILLMService(provider="groq", api_key=None)

        err_msg = str(exc_info.value)
        assert "LLM_API_KEY is required for provider 'groq'" in err_msg
        assert "Please set LLM_API_KEY in your .env file or environment variables" in err_msg


def test_ollama_local_mode_does_not_require_api_key():
    """
    Verify that provider 'ollama' works in local/offline mode without requiring an API key.
    """
    with patch("app.services.llm.llm_service.settings.LLM_API_KEY", None):
        service = OpenAILLMService(provider="ollama", api_key=None)
        assert service.provider == "ollama"
        assert service.api_key == "ollama"
        assert "11434" in service.base_url


def test_settings_env_files_resolution():
    """
    Verify that Settings includes the backend directory .env in its candidate search paths.
    """
    backend_env_str = str(_BACKEND_DIR / ".env")
    assert backend_env_str in _ENV_FILES
    assert str(_BACKEND_DIR.parent / ".env") in _ENV_FILES


def test_tutor_endpoint_reports_configuration_error_on_missing_key(client, sample_physics_pdf):
    """
    Verify that if the LLM service raises a missing-key configuration error,
    the /api/tutor/chat endpoint catches it and returns HTTP 502 with the exact descriptive detail.
    """
    # 1. Create course and upload material
    c_res = client.post("/api/courses", json={"title": "Config Error Test Course"})
    course_id = c_res.json()["id"]

    files = {"file": ("physics.pdf", io.BytesIO(sample_physics_pdf), "application/pdf")}
    client.post(f"/api/courses/{course_id}/upload", files=files)

    # 2. Simulate a tutor service whose LLM provider is missing an API key
    class MissingKeyLLMService:
        def generate(self, *args, **kwargs):
            raise ValueError(
                "LLM_API_KEY is required for provider 'openai'. Please set LLM_API_KEY in your .env file or environment variables."
            )

    original_llm = tutor_service._llm_service
    tutor_service._llm_service = MissingKeyLLMService()

    try:
        response = client.post(
            "/api/tutor/chat",
            json={"course_id": course_id, "message": "Explain Newton's laws"}
        )
        assert response.status_code == 502
        data = response.json()
        assert "detail" in data
        assert "Tutor LLM service error: LLM_API_KEY is required for provider 'openai'" in data["detail"]
    finally:
        tutor_service._llm_service = original_llm
