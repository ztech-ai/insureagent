from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CustomerInput(Input):
    client_request_id: UUID | None = None
    name: str = Field(min_length=1, max_length=100)
    notes: str = Field(default="", max_length=4000)
    tags: list[str] = Field(default_factory=list, max_length=20)
    stage: Literal["lead", "contacted", "needs", "serving"] = "lead"


class CustomerEdit(CustomerInput):
    expected_version: int = Field(ge=1)


class RecordInput(Input):
    client_record_id: UUID
    text: str = Field(min_length=1, max_length=20000)


class RecordEdit(Input):
    expected_version: int = Field(ge=1)
    text: str = Field(min_length=1, max_length=20000)


class VersionInput(Input):
    expected_version: int = Field(ge=1)


class Resolution(VersionInput):
    customer_id: UUID | None


class SegmentResolution(Resolution):
    fact_ids: list[UUID] = Field(min_length=1, max_length=100)


class FactConfirmation(VersionInput):
    fact_ids: list[UUID] = Field(max_length=100)


class TaskInput(Input):
    client_request_id: UUID | None = None
    customer_id: UUID
    title: str = Field(min_length=1, max_length=200)
    due_at: AwareDatetime


class TaskEdit(VersionInput):
    status: Literal["open", "completed", "cancelled"]
    due_at: AwareDatetime
    outcome: str = Field(default="", max_length=1000)
