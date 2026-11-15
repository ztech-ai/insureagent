from fastapi import APIRouter, Depends, HTTPException, Request

from insureagent_api.modules.identity.auth import principal, store_for
from insureagent_api.schemas import CustomerEdit, CustomerInput

router = APIRouter(prefix="/v1/customers", tags=["customers"])


@router.post("", status_code=201)
def create(body: CustomerInput, request: Request, tenant=Depends(principal)):
    store = store_for(request)
    with store.transaction() as conn:
        if len(store.list(conn, tenant, "customer")) >= 1000:
            raise HTTPException(409, "alpha_customer_limit")
        return store.add(conn, tenant, "customer", body.model_dump())


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
        row["facts"] = [
            f
            for f in store.list(conn, tenant, "fact", related_id=customer_id)
            if f["data"]["state"] == "confirmed"
        ]
        row["tasks"] = store.list(conn, tenant, "task", related_id=customer_id)
        return row


@router.patch("/{customer_id}")
def edit(customer_id: str, body: CustomerEdit, request: Request, tenant=Depends(principal)):
    store = store_for(request)
    with store.transaction() as conn:
        row = store.get(conn, tenant, customer_id, "customer", lock=True)
        return store.change(
            conn, row, body.model_dump(exclude={"expected_version"}), body.expected_version
        )
