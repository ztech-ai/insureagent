from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class SaveState(StrEnum):
    LOCAL_ONLY = "local_only"
    UPLOADING = "uploading"
    STORED = "stored"
    DELETED = "deleted"


class ProcessingState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    PARTIAL_SUCCESS = "partial_success"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED_QUOTA = "blocked_quota"
    BLOCKED_POLICY = "blocked_policy"


class IdentityState(StrEnum):
    UNASSIGNED = "unassigned"
    AMBIGUOUS = "ambiguous"
    LINKED = "linked"


class FactState(StrEnum):
    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    SUPERSEDED = "superseded"
    RETRACTED = "retracted"


class RecordStatus(BaseModel):
    """Independent dimensions: linking never implies confirming facts.

    This is a status DTO, not the transactional state machine or authorization layer.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)
    save: SaveState = SaveState.LOCAL_ONLY
    processing: ProcessingState = ProcessingState.QUEUED
    identity: IdentityState = IdentityState.UNASSIGNED
    facts: FactState = FactState.PROPOSED
