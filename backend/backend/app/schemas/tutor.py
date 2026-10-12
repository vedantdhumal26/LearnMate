from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field

class TutorChatRequest(BaseModel):
    course_id: str = Field(..., description="Target course ID")
    message: str = Field(..., min_length=1, description="Student's query or question")
    student_id: Optional[str] = Field(default=None, description="Optional student identifier for future learning analytics")

class CitationItem(BaseModel):
    source_id: str = Field(..., description="ID of the source document")
    file_name: str = Field(..., description="Source file name")
    page: Optional[int] = Field(default=None, description="Exact 1-indexed page number in the PDF (or null for PPTX)")
    slide: Optional[int] = Field(default=None, description="Exact 1-indexed slide number in the presentation (or null for PDF)")
    start_seconds: Optional[float] = Field(default=None, description="Optional start time in seconds for video/audio")
    end_seconds: Optional[float] = Field(default=None, description="Optional end time in seconds for video/audio")
    excerpt: str = Field(..., description="Relevant textual excerpt from the source chunk")
    modality: Optional[str] = Field(default=None, description="Modality of the source (pdf, pptx_text, pptx_visual, video_transcript, youtube)")
    video_id: Optional[str] = Field(default=None, description="YouTube video ID if modality is youtube")
    canonical_url: Optional[str] = Field(default=None, description="Canonical URL if modality is youtube")

    model_config = ConfigDict(from_attributes=True)

class TutorChatResponse(BaseModel):
    answer: str = Field(..., description="Grounded tutor answer or refusal if unsupported")
    grounded: bool = Field(..., description="True if answer is supported by retrieved course material, false otherwise")
    sources: List[CitationItem] = Field(default_factory=list, description="Exact page citations supporting the answer")
    response_type: Optional[str] = Field(default=None, description="Response type: 'conversational', 'academic', or None")

    model_config = ConfigDict(from_attributes=True)
