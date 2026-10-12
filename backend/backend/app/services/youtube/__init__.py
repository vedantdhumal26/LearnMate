"""
YouTube Service Package for LearnSphere AI.
Handles URL validation, metadata extraction, transcript fetching, and chunking.
"""

from app.services.youtube.youtube_service import YouTubeService, get_youtube_service

__all__ = ["YouTubeService", "get_youtube_service"]
