from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class DomainEvent(BaseModel):
    """Metadata-only envelope. Never put customer text in queue messages.

    Producer and event_type are fixed allowlists; add entries via contract review.
    Tenant identity is not authorization: consumers must check the authoritative DB.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)
    event_id: UUID
    event_type: str = Field(pattern=r"^record\.stored$")
    schema_version: int = Field(default=1, ge=1, le=1)
    tenant_id: UUID
    entity_id: UUID
    entity_version: int = Field(ge=1)
    occurred_at: AwareDatetime
    trace_id: UUID
    producer: str = Field(pattern=r"^api$")
