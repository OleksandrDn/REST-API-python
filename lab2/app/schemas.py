from pydantic import BaseModel, Field
from typing import Optional

class Book(BaseModel):
    id: Optional[int] = None  # ID тепер необов'язковий
    title: str = Field(..., min_length=1)
    author: str = Field(..., min_length=1)
    year: int = Field(..., gt=0)
