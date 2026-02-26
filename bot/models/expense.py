from pydantic import BaseModel, field_validator
from datetime import date


class Expense(BaseModel):
    amount: float
    date: str
    category: str
    subcategory: str
    description: str

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("amount must be positive")
        return v

    @field_validator("date")
    @classmethod
    def date_must_be_valid(cls, v: str) -> str:
        date.fromisoformat(v)
        return v

    def to_dict(self) -> dict:
        return self.model_dump()
