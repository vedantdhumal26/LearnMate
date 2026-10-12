from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

class YouTubeSourceRequest(BaseModel):
    url: str = Field(..., description="Public YouTube video URL")

class YouTubeSourceResponse(BaseModel):
    source_id: str = Field(..., description="Unique ID of the created source")
    video_id: str = Field(..., description="11-character YouTube video ID")
    canonical_url: str = Field(..., description="Canonical YouTube watch URL")
    status: str = Field(..., description="Processing status: processing, ready, or failed")
    message: str = Field(..., description="User-facing status message")
    title: Optional[str] = Field(default=None, description="Video title")
    duration_seconds: Optional[float] = Field(default=None, description="Video duration in seconds")

    model_config = ConfigDict(from_attributes=True)
