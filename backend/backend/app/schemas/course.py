from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field, field_validator

class CourseBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Course title")
    description: Optional[str] = Field(default=None, description="Course description")

class CourseCreate(CourseBase):
    pass

class CourseUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255, description="Course title")
    description: Optional[str] = Field(default=None, description="Course description")

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            clean = v.strip()
            if not clean:
                raise ValueError("Course title cannot be blank or whitespace-only.")
            return clean
        return None

class CourseResponse(CourseBase):
    id: str
    owner_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class SourceSummary(BaseModel):
    id: str
    file_name: str
    file_type: str
    processing_status: str
    source_type: Optional[str] = None
    title: Optional[str] = None
    video_id: Optional[str] = None
    canonical_url: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class CourseDetailResponse(CourseResponse):
    sources: List[SourceSummary] = []
    chunk_count: int = 0

    model_config = ConfigDict(from_attributes=True)
