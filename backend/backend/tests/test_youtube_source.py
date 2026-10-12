import pytest
from unittest.mock import patch, MagicMock
from app.models.source import Source
from app.models.document_chunk import DocumentChunk
from app.services.youtube.youtube_service import (
    parse_youtube_url,
    InvalidYouTubeURLError,
    YouTubeUnavailableError,
    YouTubePrivateError,
    TranscriptUnavailableError,
    YouTubeVideoMetadata,
    TranscriptSegment,
    YouTubeService,
)
from app.services.rag.citation import CitationBuilder
from app.services.vector_store.base import VectorSearchResult

def test_url_parsing_supported_formats():
    """Verify supported YouTube URL formats produce expected video_id and canonical_url."""
    test_cases = [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtube.com/v/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://m.youtube.com/watch?v=dQw4w9WgXcQ&t=120s", "dQw4w9WgXcQ"),
        ("http://youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ]

    for raw_url, expected_id in test_cases:
        vid, canonical = parse_youtube_url(raw_url)
        assert vid == expected_id, f"Failed for {raw_url}: got {vid}"
        assert canonical == f"https://www.youtube.com/watch?v={expected_id}"

def test_url_parsing_invalid_urls():
    """Reject invalid URLs cleanly with InvalidYouTubeURLError."""
    invalid_cases = [
        "https://vimeo.com/12345678",
        "https://dailymotion.com/video/x7tgad0",
        "https://www.youtube.com/watch",
        "https://www.youtube.com/watch?v=tooshort",
        "https://www.youtube.com/watch?v=waytoolongvideoid123",
        "not_a_url_at_all",
        "",
        "http://",
    ]

    for bad_url in invalid_cases:
        with pytest.raises(InvalidYouTubeURLError):
            parse_youtube_url(bad_url)

def test_metadata_failures():
    """Verify clean errors when video is unavailable, deleted, or private."""
    service = YouTubeService()

    # Simulate 404 Not Found from oEmbed
    import urllib.error
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://youtube.com/oembed",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=None
        )
        with pytest.raises(YouTubeUnavailableError) as exc_info:
            service.get_metadata("invalid12345")
        assert "unavailable or has been deleted" in str(exc_info.value)

    # Simulate 403 Forbidden from oEmbed
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://youtube.com/oembed",
            code=403,
            msg="Forbidden",
            hdrs={},
            fp=None
        )
        with pytest.raises(YouTubePrivateError) as exc_info:
            service.get_metadata("private12345")
        assert "private" in str(exc_info.value) or "restricted" in str(exc_info.value)

def test_transcript_unavailable():
    """Verify TranscriptUnavailableError is raised when no captions exist."""
    service = YouTubeService()

    # Return Innertube response with empty captionTracks
    mock_response = MagicMock()
    mock_response.read.return_value = json_bytes({
        "playabilityStatus": {"status": "OK"},
        "videoDetails": {"title": "Silent Video", "lengthSeconds": "120"},
        "captions": {"playerCaptionsTracklistRenderer": {"captionTracks": []}}
    })

    with patch("urllib.request.urlopen", return_value=mock_response):
        with pytest.raises(TranscriptUnavailableError) as exc_info:
            service.get_transcript("nocaptions11")
        assert "No transcript or captions are available" in str(exc_info.value)

def test_timestamp_preservation():
    """Verify start_time_seconds and end_time_seconds are preserved in contiguous chunks."""
    service = YouTubeService()
    segments = [
        TranscriptSegment(text="First sentence.", start_seconds=1.5, end_seconds=6.0),
        TranscriptSegment(text="Second sentence.", start_seconds=6.0, end_seconds=14.5),
        TranscriptSegment(text="Third sentence.", start_seconds=14.5, end_seconds=32.0),
    ]

    chunks = service.combine_segments_into_chunks(
        segments=segments,
        course_id="test-course-id",
        source_id="test-source-id",
        file_name="Lecture Video",
        video_id="aircAruvnKk",
        canonical_url="https://www.youtube.com/watch?v=aircAruvnKk",
        target_chunk_seconds=15.0,
        min_words_per_chunk=3
    )

    assert len(chunks) >= 1
    assert chunks[0].start_time_seconds == 1.5
    assert chunks[0].modality == "youtube"
    assert chunks[0].video_id == "aircAruvnKk"
    assert chunks[0].canonical_url == "https://www.youtube.com/watch?v=aircAruvnKk"
    assert chunks[-1].end_time_seconds == 32.0

def test_youtube_citation_generation():
    """Verify YouTube citations include display format [YouTube 00:03:42–00:04:15] and metadata."""
    chunk = VectorSearchResult(
        chunk_id="chunk-yt-001",
        course_id="course-001",
        source_id="source-yt-001",
        file_name="Deep Learning Chapter 1",
        page_number=None,
        slide_number=None,
        start_time_seconds=222.0,  # 00:03:42
        end_time_seconds=255.0,    # 00:04:15
        content="Neural networks are composed of layers of neurons.",
        score=0.92,
        modality="youtube",
        video_id="aircAruvnKk",
        canonical_url="https://www.youtube.com/watch?v=aircAruvnKk"
    )

    citations = CitationBuilder.build_citations([chunk])
    assert len(citations) == 1
    c = citations[0]
    assert c.source_id == "source-yt-001"
    assert c.file_name == "Deep Learning Chapter 1"
    assert c.modality == "youtube"
    assert c.video_id == "aircAruvnKk"
    assert c.canonical_url == "https://www.youtube.com/watch?v=aircAruvnKk"
    assert c.start_seconds == 222.0
    assert c.end_seconds == 255.0
    assert "[YouTube 00:03:42–00:04:15]" in c.excerpt
    assert "Neural networks are composed of layers of neurons." in c.excerpt

def test_add_youtube_source_api_success(client, db_session):
    """Test POST /api/courses/{course_id}/youtube endpoint with mocked YouTube service."""
    # 1. Create course
    course_res = client.post("/api/courses", json={"title": "Introduction to AI"})
    assert course_res.status_code == 201
    course_id = course_res.json()["id"]

    mock_metadata = YouTubeVideoMetadata(
        video_id="aircAruvnKk",
        canonical_url="https://www.youtube.com/watch?v=aircAruvnKk",
        title="But what is a neural network?",
        duration_seconds=1120.0,
        author="3Blue1Brown"
    )
    mock_segments = [
        TranscriptSegment(text="A neural network is inspired by biological neurons.", start_seconds=0.0, end_seconds=15.0),
        TranscriptSegment(text="Each neuron has activations between zero and one.", start_seconds=15.0, end_seconds=30.0),
    ]

    with patch("app.services.youtube.youtube_service.YouTubeService.get_metadata", return_value=mock_metadata), \
         patch("app.services.youtube.youtube_service.YouTubeService.get_transcript", return_value=mock_segments):

        res = client.post(
            f"/api/courses/{course_id}/youtube",
            json={"url": "https://www.youtube.com/watch?v=aircAruvnKk"}
        )
        assert res.status_code == 201
        data = res.json()
        assert data["video_id"] == "aircAruvnKk"
        assert data["canonical_url"] == "https://www.youtube.com/watch?v=aircAruvnKk"
        assert data["status"] in ("ready", "completed")
        assert "source_id" in data
        source_id = data["source_id"]

        # Check Course details endpoint exposes YouTube metadata
        c_res = client.get(f"/api/courses/{course_id}")
        assert c_res.status_code == 200
        course_data = c_res.json()
        assert len(course_data["sources"]) == 1
        src = course_data["sources"][0]
        assert src["source_type"] == "youtube"
        assert src["video_id"] == "aircAruvnKk"

        # Check upload/source status endpoint
        s_res = client.get(f"/api/courses/{course_id}/uploads/{source_id}")
        assert s_res.status_code == 200
        status_data = s_res.json()
        assert status_data["source_type"] == "youtube"
        assert status_data["video_id"] == "aircAruvnKk"
        assert status_data["chunks_count"] >= 1

def test_add_youtube_source_invalid_url(client):
    """POST /api/courses/{course_id}/youtube with an invalid URL returns 400."""
    course_res = client.post("/api/courses", json={"title": "Test Course"})
    course_id = course_res.json()["id"]

    res = client.post(
        f"/api/courses/{course_id}/youtube",
        json={"url": "https://notyoutube.com/video123"}
    )
    assert res.status_code == 400
    assert "Invalid YouTube" in res.json()["detail"]

def test_add_youtube_source_course_not_found(client):
    """POST /api/courses/{course_id}/youtube with non-existent course returns 404."""
    res = client.post(
        "/api/courses/non-existent-course-id/youtube",
        json={"url": "https://www.youtube.com/watch?v=aircAruvnKk"}
    )
    assert res.status_code == 404

def test_course_isolation_for_youtube_vectors(client, db_session):
    """Verify that chunks indexed for Course 1 are never retrieved in Course 2."""
    c1_res = client.post("/api/courses", json={"title": "Course 1: Neural Networks"})
    c1_id = c1_res.json()["id"]

    c2_res = client.post("/api/courses", json={"title": "Course 2: Ancient History"})
    c2_id = c2_res.json()["id"]

    mock_metadata = YouTubeVideoMetadata(
        video_id="aircAruvnKk",
        canonical_url="https://www.youtube.com/watch?v=aircAruvnKk",
        title="Neural Networks Explanation",
        duration_seconds=600.0
    )
    mock_segments = [
        TranscriptSegment(
            text="Backpropagation calculates the gradient of the cost function with respect to weights.",
            start_seconds=10.0,
            end_seconds=25.0
        )
    ]

    with patch("app.services.youtube.youtube_service.YouTubeService.get_metadata", return_value=mock_metadata), \
         patch("app.services.youtube.youtube_service.YouTubeService.get_transcript", return_value=mock_segments):

        upload_res = client.post(
            f"/api/courses/{c1_id}/youtube",
            json={"url": "https://www.youtube.com/watch?v=aircAruvnKk"}
        )
        assert upload_res.status_code == 201

    # Query Course 1: should retrieve
    from app.services.vector_store.qdrant_store import get_vector_store
    from app.services.embeddings.embedding_service import get_embedding_service
    vs = get_vector_store()
    emb = get_embedding_service()

    q_vec = emb.embed_query("backpropagation cost function")
    c1_results = vs.search_vectors(query_vector=q_vec, course_id=c1_id, limit=5)
    assert len(c1_results) > 0
    assert c1_results[0].modality == "youtube"
    assert c1_results[0].video_id == "aircAruvnKk"

    # Query Course 2: should be strictly isolated and return empty
    c2_results = vs.search_vectors(query_vector=q_vec, course_id=c2_id, limit=5)
    assert len(c2_results) == 0

def json_bytes(obj):
    import json
    return json.dumps(obj).encode("utf-8")
