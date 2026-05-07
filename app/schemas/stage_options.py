from pydantic import BaseModel
from enum import Enum


class StageOptions(str, Enum):
    separated1: str = "separated1"
    separated2: str = "separated2"
    transcribe: str = "transcribe"
