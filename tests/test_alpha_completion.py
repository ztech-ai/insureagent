import json

import pytest
from insureagent_ai.extraction.model import extract_with_model, request_local
from insureagent_worker.processor import Processor
from test_alpha import add_record, customer

pytest_plugins = ["test_alpha"]


def test_multicustomer_segments_and_retraction(alpha):
    client, store, alice, bob, _ = alpha
    a = customer(client, alice, "陈敏")
    b = customer(client, alice, "王强")
    record = add_record(client, alice, "客户陈敏，想了解家庭保障。客户王强，预算用于养老保险。")
    Processor(store).run_once()
    path = "/v1/records/" + record["id"]
    row = client.get(path, headers=alice).json()
    assert (
        client.post(
            path + "/resolution",
            headers=alice,
            json={"expected_version": row["version"], "customer_id": a["id"]},
        ).status_code
        == 409
    )
    for fact, target in zip(row["facts"], [a, b], strict=True):
        response = client.post(
            path + "/segments/resolution",
            headers=alice,
            json={
                "expected_version": row["version"],
                "customer_id": target["id"],
                "fact_ids": [fact["id"]],
            },
        )
        assert response.status_code == 200
        row = response.json()
    assert all(f["data"]["state"] == "proposed" for f in row["facts"])
    ids = [f["id"] for f in row["facts"]]
    row = client.post(
        path + "/facts/confirm",
        headers=alice,
        json={"expected_version": row["version"], "fact_ids": ids},
    ).json()
    for target in (a, b):
        profile = client.get("/v1/customers/" + target["id"], headers=alice).json()
        assert len(profile["facts"]) == 1
        assert profile["records"][0]["id"] == record["id"]
    assert (
        client.post(
            path + "/segments/resolution",
            headers=bob,
            json={"expected_version": row["version"], "customer_id": a["id"], "fact_ids": ids},
        ).status_code
        == 404
    )
    response = client.post(
        path + "/facts/retract",
        headers=alice,
        json={"expected_version": row["version"], "fact_ids": ids},
    )
    assert response.status_code == 200
    assert all(f["data"]["state"] == "proposed" for f in response.json()["facts"])


def test_request_ids_usage_and_limiter(alpha):
    client, store, alice, bob, _ = alpha
    add_record(client, alice)
    Processor(store).run_once()
    usage = client.get("/v1/usage", headers=alice)
    assert usage.json()["extraction_characters"] > 0
    assert usage.json()["billable"] is False
    assert client.get("/v1/usage", headers=bob).json()["extraction_characters"] == 0
    response = client.get("/v1/customers")
    assert response.headers["x-request-id"] == response.json()["request_id"]
    for _ in range(20):
        response = client.post(
            "/v1/sessions", json={"username": "unknown", "password": "bad-password"}
        )
    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"


def test_model_accepts_only_source_backed_selection():
    captured = []

    def transport(url, payload):
        captured.append(json.dumps(payload, ensure_ascii=False))
        return {"message": {"content": '{"selected_indices": [0]}'}}

    result = extract_with_model(
        "客户陈敏，保险预算，电话13800138000。",
        endpoint="unused",
        model="synthetic-contract",
        transport=transport,
    )
    assert "13800138000" not in captured[0]
    assert len(result["candidates"]) == 1
    assert result["candidates"][0]["evidence"].endswith("13800138000")
    with pytest.raises(ValueError, match="ungrounded"):
        extract_with_model(
            "家庭保障。",
            endpoint="unused",
            model="test",
            transport=lambda *a: {"message": {"content": '{"selected_indices": [99]}'}},
        )
    for endpoint in ("https://external.example/api/chat", "http://127.0.0.1@external.example"):
        with pytest.raises(ValueError, match="local_model_endpoint"):
            request_local(endpoint, {})


def test_task_and_customer_idempotency(alpha):
    from uuid import uuid4

    client, _, alice, _, _ = alpha
    data = {"name": "合成客户", "client_request_id": str(uuid4())}
    first = client.post("/v1/customers", headers=alice, json=data).json()
    assert client.post("/v1/customers", headers=alice, json=data).json()["id"] == first["id"]
    assert (
        client.post("/v1/customers", headers=alice, json={**data, "name": "另一人"}).status_code
        == 409
    )
    task = {
        "client_request_id": str(uuid4()),
        "customer_id": first["id"],
        "title": "核实保险需求",
        "due_at": "2026-12-01T10:00:00+08:00",
    }
    a = client.post("/v1/tasks", headers=alice, json=task).json()
    assert client.post("/v1/tasks", headers=alice, json=task).json()["id"] == a["id"]
    assert (
        client.post("/v1/tasks", headers=alice, json={**task, "title": "变更"}).status_code == 409
    )


def test_prelinked_multi_person_record_does_not_confirm_wrong_customer(alpha):
    client, store, alice, _, _ = alpha
    target = customer(client, alice)
    row = add_record(client, alice, "客户陈敏，了解家庭保险。客户王强，关注养老保险。")
    path = "/v1/records/" + row["id"]
    client.post(
        path + "/resolution",
        headers=alice,
        json={"expected_version": row["version"], "customer_id": target["id"]},
    )
    Processor(store).run_once()
    result = client.get(path, headers=alice).json()
    assert result["related_id"] is None
    assert all(f["related_id"] is None for f in result["facts"])


def test_worker_rejects_ungrounded_evidence(alpha):
    client, store, alice, _, _ = alpha
    row = add_record(client, alice)
    Processor(
        store,
        extractor=lambda text: {
            "person_names": [],
            "candidates": [{"start": 0, "end": 2, "evidence": "虚构"}],
        },
    ).run_once()
    result = client.get("/v1/records/" + row["id"], headers=alice).json()
    assert result["data"]["processing"] == "failed"
    assert result["facts"] == []
