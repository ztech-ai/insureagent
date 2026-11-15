from fastapi import APIRouter, Depends, Request
from insureagent_persistence.idempotency import create_once

from insureagent_api.modules.identity.auth import principal, store_for
from insureagent_api.schemas import TaskEdit, TaskInput

router = APIRouter(prefix="/v1/tasks", tags=["tasks"])


@router.get("")
def listing(request: Request, tenant=Depends(principal)):
    store = store_for(request)
    with store.transaction() as conn:
        return store.list(conn, tenant, "task")


@router.post("", status_code=201)
def create(body: TaskInput, request: Request, tenant=Depends(principal)):
    store = store_for(request)
    with store.transaction() as conn:
        store.get(conn, tenant, str(body.customer_id), "customer")
        return create_once(
            store,
            conn,
            tenant,
            "task",
            body.client_request_id,
            {
                "title": body.title,
                "due_at": body.due_at.isoformat(),
                "status": "open",
                "outcome": "",
            },
            related_id=str(body.customer_id),
        )


@router.patch("/{task_id}")
def edit(task_id: str, body: TaskEdit, request: Request, tenant=Depends(principal)):
    store = store_for(request)
    with store.transaction() as conn:
        row = store.get(conn, tenant, task_id, "task", lock=True)
        return store.change(
            conn,
            row,
            {
                **row["data"],
                "status": body.status,
                "due_at": body.due_at.isoformat(),
                "outcome": body.outcome,
            },
            body.expected_version,
        )
