import re
import json
import uuid
import html
import urllib.request
import urllib.error
from urllib.parse import urlparse, parse_qs
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field

from app.core.logging_config import logger
from app.utils.hashing import generate_chunk_hash
from app.services.ingestion.pdf_processor import ExtractedChunk

class InvalidYouTubeURLError(ValueError):
    """Raised when an invalid or unsupported YouTube URL is provided."""
    pass

class YouTubeUnavailableError(Exception):
    """Raised when a YouTube video is unavailable or deleted."""
    pass

class YouTubePrivateError(Exception):
    """Raised when a YouTube video is private or restricted."""
    pass

class YouTubeNotEmbeddableError(Exception):
    """Raised when a YouTube video has embedding disabled."""
    pass

class TranscriptUnavailableError(Exception):
    """Raised when no captions or transcripts are available for the video."""
    pass

class YouTubeVideoMetadata(BaseModel):
    video_id: str
    canonical_url: str
    title: str
    duration_seconds: Optional[float] = None
    author: Optional[str] = None
    is_embeddable: bool = True
    is_playable: bool = True

class TranscriptSegment(BaseModel):
    text: str
    start_seconds: float
    end_seconds: float

def parse_youtube_url(url: str) -> Tuple[str, str]:
    """
    Validate and extract video_id and canonical_url from supported YouTube URL forms:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://www.youtube.com/embed/VIDEO_ID
    - https://www.youtube.com/v/VIDEO_ID
    - https://www.youtube.com/shorts/VIDEO_ID
    - http/https, with or without www or m.
    - with additional query params (&t=10s, &feature=...)

    Returns (video_id, canonical_url)
    Raises InvalidYouTubeURLError on invalid format.
    """
    if not url or not isinstance(url, str):
        raise InvalidYouTubeURLError("YouTube URL must be a non-empty string.")

    cleaned_url = url.strip()
    if not cleaned_url.startswith(("http://", "https://")):
        cleaned_url = "https://" + cleaned_url

    try:
        parsed = urlparse(cleaned_url)
    except Exception as e:
        raise InvalidYouTubeURLError(f"Malformed URL: {e}")

    hostname = (parsed.hostname or "").lower()
    valid_hosts = {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "music.youtube.com",
        "youtu.be",
        "www.youtu.be",
    }

    if hostname not in valid_hosts and not any(hostname.endswith("." + h) for h in valid_hosts):
        raise InvalidYouTubeURLError(
            f"Invalid YouTube host '{hostname}'. URL must point to youtube.com or youtu.be."
        )

    video_id: Optional[str] = None
    path = parsed.path.strip("/")

    if hostname in ("youtu.be", "www.youtu.be"):
        # Format: https://youtu.be/VIDEO_ID
        parts = path.split("/")
        if parts and parts[0]:
            video_id = parts[0]
    else:
        # Standard youtube.com domain
        if path == "watch":
            query_params = parse_qs(parsed.query)
            v_list = query_params.get("v")
            if v_list and v_list[0]:
                video_id = v_list[0]
        elif path.startswith("embed/"):
            parts = path.split("/")
            if len(parts) >= 2 and parts[1]:
                video_id = parts[1]
        elif path.startswith("v/"):
            parts = path.split("/")
            if len(parts) >= 2 and parts[1]:
                video_id = parts[1]
        elif path.startswith("shorts/"):
            parts = path.split("/")
            if len(parts) >= 2 and parts[1]:
                video_id = parts[1]
        else:
            # Check if query parameter v exists anyway
            query_params = parse_qs(parsed.query)
            v_list = query_params.get("v")
            if v_list and v_list[0]:
                video_id = v_list[0]

    # Validate video_id format (standard YouTube video IDs are 11 chars: [a-zA-Z0-9_-]{11})
    if not video_id or not re.match(r"^[a-zA-Z0-9_-]{11}$", video_id):
        raise InvalidYouTubeURLError(
            "Could not extract a valid 11-character YouTube video ID. "
            "Supported forms: youtube.com/watch?v=VIDEO_ID, youtu.be/VIDEO_ID, youtube.com/embed/VIDEO_ID."
        )

    canonical_url = f"https://www.youtube.com/watch?v={video_id}"
    return video_id, canonical_url

class YouTubeService:
    def __init__(self, user_agent: Optional[str] = None):
        self.user_agent = user_agent or "com.google.android.youtube/20.10.38 (Linux; U; Android 14)"
        self.browser_ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        )

    def extract_url(self, url: str) -> Tuple[str, str]:
        """Validate URL and extract video_id and canonical_url."""
        return parse_youtube_url(url)

    def get_metadata(self, video_id: str) -> YouTubeVideoMetadata:
        """
        Retrieve metadata for a public YouTube video using official/allowed mechanisms.
        Handles unavailable, private, deleted, and non-embeddable videos with clear errors.
        """
        canonical_url = f"https://www.youtube.com/watch?v={video_id}"
        title = None
        author = None
        duration_seconds = None
        is_embeddable = True

        # 1. First check official YouTube oEmbed endpoint (validates public & embeddable status)
        oembed_url = f"https://www.youtube.com/oembed?url={canonical_url}&format=json"
        oembed_req = urllib.request.Request(
            oembed_url,
            headers={"User-Agent": self.browser_ua}
        )

        try:
            with urllib.request.urlopen(oembed_req, timeout=10.0) as resp:
                if resp.status == 200:
                    oembed_data = json.loads(resp.read().decode("utf-8"))
                    title = oembed_data.get("title")
                    author = oembed_data.get("author_name")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise YouTubeUnavailableError(
                    f"YouTube video '{video_id}' is unavailable or has been deleted (HTTP 404)."
                )
            elif e.code in (401, 403):
                raise YouTubePrivateError(
                    f"YouTube video '{video_id}' is private, restricted, or embedding is disabled (HTTP {e.code})."
                )
            else:
                logger.warning(f"oEmbed check returned HTTP {e.code} for video {video_id}: {e}")
        except Exception as e:
            logger.warning(f"oEmbed check failed for video {video_id}: {e}")

        # 2. Check Innertube player response for duration and playability status
        innertube_url = "https://www.youtube.com/youtubei/v1/player"
        payload = {
            "context": {
                "client": {
                    "clientName": "ANDROID",
                    "clientVersion": "20.10.38",
                    "hl": "en",
                    "gl": "US"
                }
            },
            "videoId": video_id
        }

        req = urllib.request.Request(
            innertube_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "User-Agent": self.user_agent
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                playability = data.get("playabilityStatus", {})
                status = playability.get("status", "OK")
                reason = playability.get("reason", "")

                if status != "OK":
                    reason_lower = reason.lower()
                    if "private" in reason_lower or status == "LOGIN_REQUIRED":
                        raise YouTubePrivateError(f"YouTube video '{video_id}' is private: {reason}")
                    elif "unavailable" in reason_lower or status in ("ERROR", "UNPLAYABLE"):
                        raise YouTubeUnavailableError(f"YouTube video '{video_id}' is unavailable: {reason}")
                    else:
                        raise YouTubeUnavailableError(f"YouTube video '{video_id}' cannot be played: {reason}")

                video_details = data.get("videoDetails", {})
                if not title:
                    title = video_details.get("title")
                if not author:
                    author = video_details.get("author")
                raw_len = video_details.get("lengthSeconds")
                if raw_len:
                    try:
                        duration_seconds = float(raw_len)
                    except (ValueError, TypeError):
                        pass
        except (YouTubePrivateError, YouTubeUnavailableError, YouTubeNotEmbeddableError):
            raise
        except Exception as e:
            logger.warning(f"Innertube metadata retrieval note for {video_id}: {e}")

        if not title:
            title = f"YouTube Video ({video_id})"

        return YouTubeVideoMetadata(
            video_id=video_id,
            canonical_url=canonical_url,
            title=title.strip(),
            duration_seconds=duration_seconds,
            author=author,
            is_embeddable=is_embeddable,
            is_playable=True
        )

    def get_transcript(self, video_id: str) -> List[TranscriptSegment]:
        """
        Retrieve transcript segments with exact start_seconds and end_seconds.
        Uses allowed caption tracks without downloading or storing audiovisual data.
        Raises TranscriptUnavailableError if no captions/transcripts are available.
        """
        segments: List[TranscriptSegment] = []

        # 1. Fetch caption tracks from Innertube player response
        innertube_url = "https://www.youtube.com/youtubei/v1/player"
        payload = {
            "context": {
                "client": {
                    "clientName": "ANDROID",
                    "clientVersion": "20.10.38",
                    "hl": "en",
                    "gl": "US"
                }
            },
            "videoId": video_id
        }

        req = urllib.request.Request(
            innertube_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "User-Agent": self.user_agent
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=12.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                playability = data.get("playabilityStatus", {})
                if playability.get("status") not in ("OK", None):
                    reason = playability.get("reason", "Video is not playable")
                    if "private" in reason.lower():
                        raise YouTubePrivateError(f"Video is private: {reason}")
                    raise YouTubeUnavailableError(f"Video is unavailable: {reason}")

                tracks = (
                    data.get("captions", {})
                    .get("playerCaptionsTracklistRenderer", {})
                    .get("captionTracks", [])
                )

                if tracks:
                    # Select best track: English first, or first available track
                    selected_track = next(
                        (t for t in tracks if (t.get("languageCode") or "").lower().startswith("en")),
                        tracks[0]
                    )
                    base_url = selected_track.get("baseUrl")
                    if base_url:
                        segments = self._fetch_timedtext_xml(base_url)
        except (YouTubePrivateError, YouTubeUnavailableError, TranscriptUnavailableError):
            raise
        except Exception as e:
            logger.warning(f"Innertube caption retrieval error for {video_id}: {e}")

        # 2. Fallback: try youtube_transcript_api if available
        if not segments:
            try:
                from youtube_transcript_api import YouTubeTranscriptApi
                ytt = YouTubeTranscriptApi()
                raw_segments = ytt.fetch(video_id)
                for s in raw_segments:
                    text = clean_text(s.get("text", ""))
                    if text:
                        start = float(s.get("start", 0.0))
                        dur = float(s.get("duration", 0.0))
                        segments.append(
                            TranscriptSegment(
                                text=text,
                                start_seconds=round(start, 2),
                                end_seconds=round(start + dur, 2)
                            )
                        )
            except Exception as ytt_err:
                logger.debug(f"youtube_transcript_api fallback note for {video_id}: {ytt_err}")

        if not segments:
            raise TranscriptUnavailableError(
                f"No transcript or captions are available for YouTube video '{video_id}'. "
                f"Please ensure the video is public and has closed captions or subtitles enabled."
            )

        logger.info(f"Retrieved {len(segments)} transcript segments for YouTube video {video_id}")
        return segments

    def _fetch_timedtext_xml(self, base_url: str) -> List[TranscriptSegment]:
        """Fetch and parse timedtext XML into TranscriptSegment objects."""
        import xml.etree.ElementTree as ET

        req = urllib.request.Request(
            base_url,
            headers={"User-Agent": self.user_agent}
        )

        with urllib.request.urlopen(req, timeout=12.0) as resp:
            raw_content = resp.read().decode("utf-8", errors="ignore")

        if not raw_content:
            return []

        segments: List[TranscriptSegment] = []
        try:
            root = ET.fromstring(raw_content)
            # Standard format: <p t="ms" d="ms">text</p>
            for p in root.findall(".//p"):
                raw_text = "".join(p.itertext()).strip()
                cleaned = clean_text(raw_text)
                if not cleaned:
                    continue

                t_ms = float(p.attrib.get("t", 0.0))
                d_ms = float(p.attrib.get("d", 0.0))
                start_sec = round(t_ms / 1000.0, 2)
                end_sec = round((t_ms + d_ms) / 1000.0, 2)
                if end_sec <= start_sec:
                    end_sec = start_sec + 2.0

                segments.append(
                    TranscriptSegment(
                        text=cleaned,
                        start_seconds=start_sec,
                        end_seconds=end_sec
                    )
                )

            # Alternate format: <text start="s" dur="s">text</text>
            if not segments:
                for t in root.findall(".//text"):
                    raw_text = "".join(t.itertext()).strip()
                    cleaned = clean_text(raw_text)
                    if not cleaned:
                        continue

                    start_sec = float(t.attrib.get("start", 0.0))
                    dur_sec = float(t.attrib.get("dur", 2.0))
                    segments.append(
                        TranscriptSegment(
                            text=cleaned,
                            start_seconds=round(start_sec, 2),
                            end_seconds=round(start_sec + dur_sec, 2)
                        )
                    )
        except Exception as e:
            logger.warning(f"Error parsing timedtext XML: {e}")

        return segments

    def combine_segments_into_chunks(
        self,
        segments: List[TranscriptSegment],
        course_id: str,
        source_id: str,
        file_name: str,
        video_id: str,
        canonical_url: str,
        target_chunk_seconds: float = 30.0,
        min_words_per_chunk: int = 20,
        overlap_seconds: float = 8.0,
    ) -> List[ExtractedChunk]:
        """
        Group contiguous transcript segments into time-window chunks while strictly
        preserving start_time_seconds, end_time_seconds, video_id, and canonical_url.
        Uses a small overlap window between adjacent chunks to prevent transcript phrase
        severing across chunk boundaries.
        """
        if not segments:
            return []

        chunks: List[ExtractedChunk] = []
        n = len(segments)
        start_idx = 0
        chunk_index = 0

        while start_idx < n:
            curr_texts = []
            chunk_start_sec = segments[start_idx].start_seconds
            end_idx = start_idx

            while end_idx < n:
                curr_texts.append(segments[end_idx].text)
                chunk_end_sec = segments[end_idx].end_seconds
                duration = chunk_end_sec - chunk_start_sec
                words = sum(len(t.split()) for t in curr_texts)

                if duration >= target_chunk_seconds and words >= min_words_per_chunk:
                    break
                end_idx += 1

            if end_idx >= n:
                end_idx = n - 1
                chunk_end_sec = segments[end_idx].end_seconds

            content = " ".join(curr_texts).strip()
            if content:
                chunk_id = str(uuid.uuid4())
                content_hash = generate_chunk_hash(course_id, chunk_index, content)
                chunks.append(
                    ExtractedChunk(
                        chunk_id=chunk_id,
                        course_id=course_id,
                        source_id=source_id,
                        file_name=file_name,
                        page_number=None,
                        slide_number=None,
                        start_time_seconds=chunk_start_sec,
                        end_time_seconds=chunk_end_sec,
                        modality="youtube",
                        visual_description=None,
                        chunk_index=chunk_index,
                        content=content,
                        content_hash=content_hash,
                        video_id=video_id,
                        canonical_url=canonical_url
                    )
                )
                chunk_index += 1

            if end_idx >= n - 1:
                break

            # Advance start_idx with overlap
            next_start_idx = end_idx + 1
            if overlap_seconds > 0:
                for back_idx in range(end_idx, start_idx, -1):
                    if (chunk_end_sec - segments[back_idx].start_seconds) <= overlap_seconds:
                        next_start_idx = back_idx
                    else:
                        break

            # Guard against infinite loops: ensure forward progress
            if next_start_idx <= start_idx:
                next_start_idx = start_idx + 1

            start_idx = next_start_idx

        return chunks

def clean_text(raw: str) -> str:
    """Unescape HTML and normalize whitespace."""
    if not raw:
        return ""
    text = html.unescape(raw)
    # Remove bracketed artifacts like [Music], [Applause]
    text = re.sub(r"\[(?:Music|Applause|Laughter|Cheering)\]", "", text, flags=re.IGNORECASE)
    return " ".join(text.strip().split())

_youtube_service_instance: Optional[YouTubeService] = None

def get_youtube_service() -> YouTubeService:
    global _youtube_service_instance
    if _youtube_service_instance is None:
        _youtube_service_instance = YouTubeService()
    return _youtube_service_instance
