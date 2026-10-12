import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import SessionLocal
from app.models.source import Source
from app.models.document_chunk import DocumentChunk
from app.models.course import Course

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

db = SessionLocal()
sources = db.query(Source).all()
print(f"Total sources in DB: {len(sources)}")
for s in sources:
    c = db.query(Course).filter(Course.id == s.course_id).first()
    c_title = c.title if c else "Unknown"
    chunks = db.query(DocumentChunk).filter(DocumentChunk.source_id == s.id).all()
    print(f"Source [{s.source_type}]: {s.file_name} (id={s.id}, course={s.course_id[:8]} '{c_title[:30]}', chunks={len(chunks)})")
db.close()
