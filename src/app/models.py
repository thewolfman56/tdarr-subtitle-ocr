from __future__ import annotations

from pydantic import BaseModel, Field


class OcrRequest(BaseModel):
    input_path: str = Field(min_length=1)
    output_path: str = Field(min_length=1)
    language: str = Field(default="eng", min_length=1, max_length=32)
    language2: str | None = Field(default=None, max_length=32)
    language3: str | None = Field(default=None, max_length=32)


class OcrResponse(BaseModel):
    ok: bool
    job_id: str
    engine: str
    output_path: str
    message: str
