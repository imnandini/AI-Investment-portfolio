from pydantic import BaseModel

from app.schemas.portfolio import HoldingRead


class ImportRowError(BaseModel):
    row: int
    field: str | None = None
    message: str


class HoldingsImportResponse(BaseModel):
    imported_count: int
    errors: list[ImportRowError]
    holdings: list[HoldingRead]
