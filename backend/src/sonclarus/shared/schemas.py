from __future__ import annotations
from typing import Any, Optional, TypeVar
from pydantic import BaseModel, Field, field_validator

from src.sonclarus.shared.utilities import reject_blank_text

T = TypeVar("T")


# --- Schema of Global Api Response ---
class ApiResponseSchema(BaseModel):
    """Pydantic schema of global api response"""

    message: str = Field(min_length=1, max_length=500)
    status_code: int
    data: Optional[T] = None
    meta: Optional[dict[str, Any]] = None

    _validate_text = field_validator("message", mode="before")(reject_blank_text)
