from enum import Enum
from typing import Any

from pydantic.main import BaseModel


class HistoryMonthEnum(int, Enum):
    One = 1
    Two = 2
    Three = 3
    Four = 4
    Five = 5
    Six = 6


class HistoryMonth(BaseModel):
    month: HistoryMonthEnum


class Response(BaseModel):
    success: bool = True
    message: str = None
    data: Any
    error_code: int = 0
