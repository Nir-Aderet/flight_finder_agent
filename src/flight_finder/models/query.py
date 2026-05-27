from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

IATACode = Annotated[str, Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")]
CurrencyCode = Annotated[str, Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")]


class FlightSearchRequest(BaseModel):
    origin: IATACode
    destination: IATACode
    depart_date: date
    return_date: date | None = None
    passengers: int = Field(default=1, ge=1, le=9)
    cabin: Literal["economy", "premium", "business", "first"] = "economy"
    max_stops: int | None = Field(default=None, ge=0)
    max_price: Decimal | None = Field(default=None, gt=0)
    preferred_airlines: list[str] = Field(default_factory=list)
    blocked_airlines: list[str] = Field(default_factory=list)
    currency: CurrencyCode = "USD"

    @model_validator(mode="after")
    def _return_date_after_depart(self) -> FlightSearchRequest:
        if self.return_date is not None and self.return_date < self.depart_date:
            raise ValueError("return_date must be on or after depart_date")
        return self
