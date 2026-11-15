import base64
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from insureagent_api.config import Settings
from insureagent_api.main import create_app
from insureagent_api.modules.identity.auth import password_hash
from insureagent_persistence.store import accounts, entities, jobs, outbox
from insureagent_worker.processor import Processor
from sqlalchemy import create_engine, insert, select, update
from sqlalchemy.engine import make_url


@pytest.fixture
def alpha(tmp_path):
    from insureagent_api.modules.identity.auth import _login_buckets

    _login_buckets.clear()
    url = os.environ.get("TEST_DATABASE_URL", f"sqlite:///{tmp_path / 'alpha.db'}")
    admin = None
    if url.startswith("postgresql"):
        admin = create_engine(url)
        schema = "test_" + uuid4().hex
        with admin.begin() as conn:
            conn.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
        url = make_url(url).update_query_dict({"options": f"-csearch_path={schema}"})
        url = url.render_as_string(hide_password=False)
    settings = Settings(url, base64.b64encode(os.urandom(32)).decode())
    app = create_app(settings)
    store = app.state.store
    store.initialize()
    with store.transaction() as conn:
        for username in ("alice", "bob"):
            conn.execute(
                insert(accounts).values(
                    id=str(uuid4()),
                    username=username,
                    password_hash=password_hash("alpha-passphrase"),
                )
            )
    client = TestClient(app)
    headers = []
    for username in ("alice", "bob"):
        response = client.post(
            "/v1/sessions", json={"username": username, "password": "alpha-passphrase"}
        )
        assert response.status_code == 200
        headers.append({"Authorization": "Bearer " + response.json()["access_token"]})
    yield client, store, headers[0], headers[1], settings
    store.engine.dispose()
    if admin:
        with admin.begin() as conn:
            conn.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
        admin.dispose()


def add_record(client, headers, text="客户陈敏，想了解家庭保障。电话13800138000。", client_id=None):
    response = client.post(
        "/v1/records",
        headers=headers,
        json={"client_record_id": client_id or str(uuid4()), "text": text},
    )
    assert response.status_code == 201, response.text
    return response.json()


def customer(client, headers, name="陈敏"):
    response = client.post("/v1/customers", headers=headers, json={"name": name})
    assert response.status_code == 201
    return response.json()


def test_authentication_and_tenant_isolation(alpha):
    client, store, alice, bob, _ = alpha
    assert client.get("/v1/customers").status_code == 401
    c = customer(client, alice)
    assert client.get("/v1/customers/" + c["id"], headers=bob).status_code == 404
    record = add_record(client, alice)
    assert client.get("/v1/records/" + record["id"], headers=bob).status_code == 404
    assert (
        client.post(
            "/v1/records/" + record["id"] + "/resolution",
            headers=bob,
            json={"expected_version": 1, "customer_id": c["id"]},
        ).status_code
        == 404
    )
    assert client.get("/v1/records", headers=bob).json() == []
    assert client.delete("/v1/sessions/current", headers=alice).status_code == 204
    assert client.get("/v1/records", headers=alice).status_code == 401


def test_durable_encryption_and_idempotency(alpha):
    client, store, alice, _, settings = alpha
    ident = str(uuid4())
    record = add_record(client, alice, client_id=ident)
    assert add_record(client, alice, client_id=ident)["id"] == record["id"]
    assert (
        client.post(
            "/v1/records", headers=alice, json={"client_record_id": ident, "text": "changed"}
        ).status_code
        == 409
    )
    with store.transaction() as conn:
        raw = conn.execute(select(entities.c.payload)).scalar_one()
        assert "家庭".encode() not in raw and b"13800138000" not in raw
        assert len(conn.execute(select(jobs)).all()) == 1
        assert len(conn.execute(select(outbox)).all()) == 1
    restarted = TestClient(create_app(settings))
    assert (
        restarted.get("/v1/records/" + record["id"], headers=alice).json()["data"]["save"]
        == "stored"
    )


def test_confirmation_correction_and_history(alpha):
    client, store, alice, _, _ = alpha
    c = customer(client, alice)
    row = add_record(client, alice)
    worker = Processor(store)
    assert worker.run_once()
    row = client.get("/v1/records/" + row["id"], headers=alice).json()
    assert row["customer_candidates"][0]["id"] == c["id"]
    assert "13800138000" not in row["data"]["redacted_text"]
    assert row["facts"][0]["data"]["state"] == "proposed"
    url = "/v1/records/" + row["id"]
    row = client.post(
        url + "/resolution",
        headers=alice,
        json={"expected_version": row["version"], "customer_id": c["id"]},
    ).json()
    assert client.get("/v1/customers/" + c["id"], headers=alice).json()["facts"] == []
    response = client.post(
        url + "/facts/confirm",
        headers=alice,
        json={"expected_version": row["version"], "fact_ids": [row["facts"][0]["id"]]},
    )
    assert response.status_code == 200
    row = response.json()
    assert len(client.get("/v1/customers/" + c["id"], headers=alice).json()["facts"]) == 1
    assert (
        client.patch(url, headers=alice, json={"expected_version": 1, "text": "stale"}).status_code
        == 409
    )
    row = client.patch(
        url,
        headers=alice,
        json={"expected_version": row["version"], "text": "客户陈敏，预算待核实。"},
    ).json()
    assert client.get("/v1/customers/" + c["id"], headers=alice).json()["facts"] == []
    assert worker.run_once()
    assert len(client.get("/v1/records?q=预算", headers=alice).json()) == 1
    row = client.get(url, headers=alice).json()
    assert row["revision"] == 2
    assert all(f["data"]["source_revision"] == 2 for f in row["facts"])


def test_old_worker_cannot_overwrite_edit_or_delete(alpha):
    client, store, alice, _, _ = alpha
    row = add_record(client, alice)
    worker = Processor(store)
    job = worker.claim()
    url = "/v1/records/" + row["id"]
    row = client.patch(
        url,
        headers=alice,
        json={"expected_version": row["version"], "text": "客户陈敏，修改保障需求。"},
    ).json()
    assert not worker.deliver(job, output=worker.extractor(job["text"]))
    new_job = worker.claim()
    assert (
        client.request(
            "DELETE", url, headers=alice, json={"expected_version": row["version"]}
        ).status_code
        == 200
    )
    assert not worker.deliver(new_job, output=worker.extractor(new_job["text"]))
    assert client.get(url, headers=alice).status_code == 404


def test_expired_lease_fences_previous_worker(alpha):
    client, store, alice, _, _ = alpha
    add_record(client, alice)
    worker = Processor(store)
    first = worker.claim()
    with store.transaction() as conn:
        conn.execute(update(jobs).values(lease_until="2000-01-01T00:00:00+00:00"))
    second = worker.claim()
    assert second["fence"] > first["fence"]
    assert not worker.deliver(first, output=worker.extractor(first["text"]))
    assert worker.deliver(second, output=worker.extractor(second["text"]))
    assert not worker.deliver(second, output=worker.extractor(second["text"]))


def test_failed_extraction_preserves_record_and_retries(alpha):
    client, store, alice, _, _ = alpha
    row = add_record(client, alice)

    def unavailable(_):
        raise RuntimeError("sensitive content must not be returned")

    assert Processor(store, unavailable).run_once()
    url = "/v1/records/" + row["id"]
    row = client.get(url, headers=alice).json()
    assert row["data"]["save"] == "stored" and row["data"]["processing"] == "failed"
    assert "sensitive content" not in str(row)
    assert (
        client.post(
            url + "/retry", headers=alice, json={"expected_version": row["version"]}
        ).status_code
        == 200
    )
    assert Processor(store).run_once()
    assert client.get(url, headers=alice).json()["data"]["processing"] == "succeeded"


def test_manual_tasks_versions_and_outcomes(alpha):
    client, _, alice, bob, _ = alpha
    c = customer(client, alice)
    row = client.post(
        "/v1/tasks",
        headers=alice,
        json={"customer_id": c["id"], "title": "核实保障", "due_at": "2026-11-20T08:00:00Z"},
    ).json()
    payload = {
        "expected_version": 1,
        "status": "completed",
        "due_at": "2026-11-21T08:00:00Z",
        "outcome": "已联系，待补充资料",
    }
    url = "/v1/tasks/" + row["id"]
    assert client.patch(url, headers=bob, json=payload).status_code == 404
    assert client.patch(url, headers=alice, json=payload).status_code == 200
    assert client.patch(url, headers=alice, json=payload).status_code == 409
    assert client.get("/v1/customers/" + c["id"], headers=alice).json()["data"]["stage"] == "lead"


def test_deleted_client_id_cannot_resurrect_record(alpha):
    client, _, alice, _, _ = alpha
    ident = str(uuid4())
    row = add_record(client, alice, client_id=ident)
    assert (
        client.request(
            "DELETE",
            "/v1/records/" + row["id"],
            headers=alice,
            json={"expected_version": row["version"]},
        ).status_code
        == 200
    )
    response = client.post(
        "/v1/records",
        headers=alice,
        json={"client_record_id": ident, "text": "replayed offline upload"},
    )
    assert response.status_code == 410
    assert client.get("/v1/records", headers=alice).json() == []


def wav_bytes(seconds=0.2, sample_rate=16000):
    import io
    import wave

    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(b"\x01\x00" * int(seconds * sample_rate))
    return output.getvalue()


def upload_audio(client, headers, raw=None, client_id=None):
    return client.post(
        "/v1/records/audio",
        headers={**headers, "Content-Type": "audio/wav"},
        params={"client_record_id": client_id or str(uuid4())},
        content=raw or wav_bytes(),
    )


def test_audio_upload_encryption_idempotence_and_deletion(alpha):
    from insureagent_persistence.store import audio_blobs

    client, store, alice, bob, _ = alpha
    ident = str(uuid4())
    raw = wav_bytes()
    response = upload_audio(client, alice, raw, ident)
    assert response.status_code == 201, response.text
    row = response.json()
    assert upload_audio(client, alice, raw, ident).json()["id"] == row["id"]
    assert upload_audio(client, alice, wav_bytes(0.3), ident).status_code == 409
    with store.transaction() as conn:
        assert raw not in conn.execute(select(audio_blobs.c.payload)).scalar_one()
    url = "/v1/records/" + row["id"]
    assert client.get(url + "/audio", headers=bob).status_code == 404
    assert client.get(url + "/audio", headers=alice).content == raw
    assert (
        client.request(
            "DELETE", url, headers=alice, json={"expected_version": row["version"]}
        ).status_code
        == 200
    )
    assert client.get(url + "/audio", headers=alice).status_code == 404
    with store.transaction() as conn:
        assert conn.execute(select(audio_blobs)).first() is None
    assert upload_audio(client, alice, raw, ident).status_code == 410


@pytest.mark.parametrize("raw", [b"not audio", wav_bytes(sample_rate=8000), wav_bytes()[:-12]])
def test_invalid_audio_does_not_create_record(alpha, raw):
    client, _, alice, _, _ = alpha
    assert upload_audio(client, alice, raw).status_code == 422
    assert client.get("/v1/records", headers=alice).json() == []


def test_audio_partial_success_retries_only_failed_extraction(alpha):
    client, store, alice, _, _ = alpha
    row = upload_audio(client, alice).json()
    calls = []

    def asr(raw, heartbeat):
        assert heartbeat()
        calls.append("asr")
        return "客户陈敏，想了解家庭保障。"

    def unavailable(_):
        raise RuntimeError("extraction unavailable")

    assert Processor(store, unavailable, asr).run_once()
    url = "/v1/records/" + row["id"]
    row = client.get(url, headers=alice).json()
    assert row["data"]["processing"] == "partial_success"
    assert row["data"]["text"] == "客户陈敏，想了解家庭保障。"
    assert (
        client.post(
            url + "/retry", headers=alice, json={"expected_version": row["version"]}
        ).status_code
        == 200
    )
    assert Processor(store, transcriber=asr).run_once()
    assert calls == ["asr"]
    assert client.get(url, headers=alice).json()["data"]["processing"] == "succeeded"


def test_audio_failure_allows_manual_transcript(alpha):
    client, store, alice, _, _ = alpha
    row = upload_audio(client, alice).json()

    def unavailable(raw, heartbeat):
        raise RuntimeError("asr unavailable")

    worker = Processor(store, transcriber=unavailable)
    assert worker.run_once()
    url = "/v1/records/" + row["id"]
    row = client.get(url, headers=alice).json()
    assert row["data"]["error_code"] == "asr_unavailable"
    assert row["data"]["save"] == "stored"
    assert (
        client.patch(
            url,
            headers=alice,
            json={"expected_version": row["version"], "text": "客户陈敏，家庭保障待核实。"},
        ).status_code
        == 200
    )
    assert worker.run_once()
    row = client.get(url, headers=alice).json()
    assert row["data"]["processing"] == "succeeded"
    assert row["data"]["asr_status"] == "manual"
