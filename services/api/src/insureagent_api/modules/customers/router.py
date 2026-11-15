from fastapi import APIRouter, Depends, HTTPException, Request
from insureagent_persistence.idempotency import create_once
from insureagent_persistence.store import accounts
from sqlalchemy import select

from insureagent_api.modules.identity.auth import principal, store_for
from insureagent_api.schemas import CustomerEdit, CustomerInput

router = APIRouter(prefix="/v1/customers", tags=["customers"])


@router.post("", status_code=201)
def create(body: CustomerInput, request: Request, tenant=Depends(principal)):
    store = store_for(request)
    with store.transaction() as conn:
        conn.execute(select(accounts.c.id).where(accounts.c.id == tenant).with_for_update())
        existing = (
            store.list(conn, tenant, "customer", client_id=str(body.client_request_id))
            if body.client_request_id
            else []
        )
        if not existing and len(store.list(conn, tenant, "customer")) >= 1000:
            raise HTTPException(409, "alpha_customer_limit")
        return create_once(
            store,
            conn,
            tenant,
            "customer",
            body.client_request_id,
            body.model_dump(exclude={"client_request_id"}),
        )


@router.get("")
def customers(request: Request, q: str = "", tenant=Depends(principal)):
    store = store_for(request)
    with store.transaction() as conn:
        rows = store.list(conn, tenant, "customer")
        term = q[:200].casefold()
        return [r for r in rows if term in str(r["data"]).casefold()]


@router.get("/{customer_id}")
def detail(customer_id: str, request: Request, tenant=Depends(principal)):
    store = store_for(request)
    with store.transaction() as conn:
        row = store.get(conn, tenant, customer_id, "customer")
        row["records"] = store.list(conn, tenant, "record", related_id=customer_id)
        associated = [
            f
            for f in store.list(conn, tenant, "fact", related_id=customer_id)
            if f["data"]["state"] != "retracted"
        ]
        row["facts"] = [f for f in associated if f["data"]["state"] == "confirmed"]
        source_ids = {f["source_id"] for f in associated}
        timeline = {r["id"]: r for r in row["records"]}
        for source_id in source_ids:
            timeline[source_id] = store.get(conn, tenant, source_id, "record")
        row["records"] = sorted(timeline.values(), key=lambda r: r["created_at"], reverse=True)
        row["tasks"] = store.list(conn, tenant, "task", related_id=customer_id)
        return row


@router.patch("/{customer_id}")
def edit(customer_id: str, body: CustomerEdit, request: Request, tenant=Depends(principal)):
    store = store_for(request)
    with store.transaction() as conn:
        row = store.get(conn, tenant, customer_id, "customer", lock=True)
        return store.change(
            conn,
            row,
            {**row["data"], **body.model_dump(exclude={"expected_version", "client_request_id"})},
            body.expected_version,
        )
