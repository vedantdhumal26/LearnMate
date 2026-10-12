from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

class UploadResponse(BaseModel):
    source_id: str = Field(..., description="Unique ID of the uploaded source")
    file_name: str = Field(..., description="Original file name")
    status: str = Field(..., description="Processing status (processing, completed, failed)")
    id: Optional[str] = Field(default=None, description="Compatibility alias for source_id")
    processing_status: Optional[str] = Field(default=None, description="Compatibility alias for status")

    model_config = ConfigDict(from_attributes=True)

class SourceStatusResponse(BaseModel):
    source_id: str
    course_id: str
    file_name: str
    file_type: str
    processing_status: str
    source_type: Optional[str] = None
    title: Optional[str] = None
    video_id: Optional[str] = None
    canonical_url: Optional[str] = None
    chunks_count: Optional[int] = 0
    slide_count: Optional[int] = None
    visual_count: Optional[int] = None
    duration_seconds: Optional[float] = None
    segment_count: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
