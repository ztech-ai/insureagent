import asyncio
import subprocess
import sys
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from insureagent_ai.gateway import DisabledModelGateway, ModelUnavailable
from insureagent_api.main import app
from insureagent_domain.events import DomainEvent
from insureagent_domain.records import RecordStatus
from pydantic import ValidationError


def event_payload():
    return dict(
        event_id=str(uuid4()),
        event_type="record.stored",
        tenant_id=str(uuid4()),
        entity_id=str(uuid4()),
        entity_version=1,
        occurred_at="2026-11-15T10:00:00Z",
        trace_id=str(uuid4()),
        producer="api",
    )


def test_liveness_does_not_claim_dependency_readiness():
    client = TestClient(app)
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 503
    assert client.post("/v1/records", json={}).status_code == 404


def test_link_and_processing_success_do_not_confirm_facts():
    status = RecordStatus(save="stored", processing="succeeded", identity="linked")
    assert status.facts == "proposed"


def test_partial_failure_preserves_durable_save_state():
    assert RecordStatus(save="stored", processing="partial_success").save == "stored"


def test_event_accepts_metadata_and_rejects_customer_payload():
    payload = event_payload()
    DomainEvent.model_validate(payload)
    with pytest.raises(ValidationError):
        DomainEvent.model_validate(dict(payload, customer_phone="sensitive-fixture"))
    with pytest.raises(ValidationError):
        DomainEvent.model_validate(dict(payload, event_type="arbitrary customer text"))


def test_worker_error_does_not_echo_input():
    result = subprocess.run(
        [sys.executable, "-m", "insureagent_worker.main", "--validate-event"],
        input=b'{"secret":"sensitive-fixture"}',
        capture_output=True,
    )
    assert result.returncode == 2
    assert b"sensitive-fixture" not in result.stdout + result.stderr


def test_model_gateway_is_disabled():
    with pytest.raises(ModelUnavailable):
        asyncio.run(DisabledModelGateway().generate("synthetic input"))
