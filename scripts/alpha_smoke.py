"""Disposable synthetic HTTP smoke demo. Creates no production accounts or retained records."""

import base64
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

import httpx
from insureagent_api.modules.identity.auth import password_hash
from insureagent_persistence.store import Store, accounts
from sqlalchemy import insert


def main():
    with tempfile.TemporaryDirectory(prefix="insureagent-smoke-") as directory:
        env = {
            **os.environ,
            "DATABASE_URL": f"sqlite:///{directory}/demo.db",
            "ALPHA_DATA_KEY": base64.b64encode(os.urandom(32)).decode(),
            "ALPHA_EXTRACTOR": "rules",
        }
        store = Store(env["DATABASE_URL"], env["ALPHA_DATA_KEY"])
        store.initialize()
        password = secrets.token_urlsafe(24)
        with store.transaction() as conn:
            conn.execute(
                insert(accounts).values(
                    id=str(uuid4()),
                    username="synthetic-demo",
                    password_hash=password_hash(password),
                )
            )
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        process = None

        def start():
            server = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "insureagent_api.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                ],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            for _ in range(100):
                try:
                    if httpx.get(f"http://127.0.0.1:{port}/health/ready").status_code == 200:
                        return server
                except httpx.TransportError:
                    pass
                time.sleep(0.05)
            server.terminate()
            server.wait(timeout=10)
            raise RuntimeError("API did not become ready")

        try:
            process = start()
            with httpx.Client(base_url=f"http://127.0.0.1:{port}") as client:
                session = client.post(
                    "/v1/sessions", json={"username": "synthetic-demo", "password": password}
                )
                session.raise_for_status()
                client.headers["Authorization"] = "Bearer " + session.json()["access_token"]
                customer = client.post("/v1/customers", json={"name": "合成客户陈敏"}).json()
                body = {
                    "client_record_id": str(uuid4()),
                    "text": "客户陈敏，想了解家庭医疗保险。下周联系核实预算。",
                }
                record = client.post("/v1/records", json=body).json()
                assert client.post("/v1/records", json=body).json()["id"] == record["id"]
                subprocess.run(
                    [sys.executable, "scripts/run_worker.py", "--once"], env=env, check=True
                )
                path = "/v1/records/" + record["id"]
                record = client.get(path).json()
                assert record["data"]["processing"] == "succeeded"
                record = client.post(
                    path + "/resolution",
                    json={"expected_version": record["version"], "customer_id": customer["id"]},
                ).json()
                record = client.post(
                    path + "/facts/confirm",
                    json={
                        "expected_version": record["version"],
                        "fact_ids": [f["id"] for f in record["facts"]],
                    },
                ).json()
                task = client.post(
                    "/v1/tasks",
                    json={
                        "customer_id": customer["id"],
                        "title": "核实家庭保障需求",
                        "due_at": "2026-12-01T09:00:00+08:00",
                    },
                ).json()
                response = client.patch(
                    "/v1/tasks/" + task["id"],
                    json={
                        "expected_version": task["version"],
                        "status": "completed",
                        "due_at": task["data"]["due_at"],
                        "outcome": "已联系，等待客户补充资料",
                    },
                )
                response.raise_for_status()
                process.terminate()
                process.wait(timeout=10)
                process = start()
                assert client.get(path).json()["data"]["save"] == "stored"
                profile = client.get("/v1/customers/" + customer["id"]).json()
                assert len(profile["facts"]) == 2
                assert profile["tasks"][0]["data"]["status"] == "completed"
                print(
                    json.dumps(
                        {
                            "result": "passed",
                            "transport": "real HTTP",
                            "scenarios": [
                                "login",
                                "durable record",
                                "idempotent replay",
                                "worker extraction",
                                "identity then facts",
                                "profile evidence",
                                "task outcome",
                                "API restart persistence",
                            ],
                            "synthetic_data_only": True,
                        },
                        indent=2,
                    )
                )
        finally:
            if process:
                process.terminate()
                process.wait(timeout=10)
            store.engine.dispose()


if __name__ == "__main__":
    main()
