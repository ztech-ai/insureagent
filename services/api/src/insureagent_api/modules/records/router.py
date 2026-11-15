from fastapi import APIRouter, Depends, HTTPException, Request
from insureagent_persistence.store import Conflict, accounts, audio_blobs, entities, jobs
from sqlalchemy import delete as sql_delete
from sqlalchemy import select

from insureagent_api.modules.identity.auth import principal, store_for
from insureagent_api.schemas import (
    FactConfirmation,
    RecordEdit,
    RecordInput,
    Resolution,
    SegmentResolution,
    VersionInput,
)

router = APIRouter(prefix="/v1/records", tags=["records"])


def invalidate_facts(store, conn, row):
    for fact in store.list(conn, row["tenant_id"], "fact", source_id=row["id"]):
        store.change(conn, fact, {**fact["data"], "state": "retracted"}, fact["version"])


def record_detail(store, conn, row):
    row["facts"] = [
        f
        for f in store.list(conn, row["tenant_id"], "fact", source_id=row["id"])
        if f["data"]["state"] != "retracted"
    ]
    job = (
        conn.execute(
            select(jobs).where(
                jobs.c.tenant_id == row["tenant_id"],
                jobs.c.record_id == row["id"],
                jobs.c.revision == row["revision"],
            )
        )
        .mappings()
        .first()
    )
    row["job"] = (
        {"state": job["state"], "attempts": job["attempts"], "error_code": job["error_code"]}
        if job
        else None
    )
    row["confirmation"] = {
        "total": len(row["facts"]),
        "confirmed": sum(f["data"]["state"] == "confirmed" for f in row["facts"]),
    }
    names = row["data"].get("person_names", [])
    row["customer_candidates"] = [
        c for c in store.list(conn, row["tenant_id"], "customer") if c["data"]["name"] in names
    ]
    return row


@router.post("", status_code=201)
def create(body: RecordInput, request: Request, tenant=Depends(principal)):
    store = store_for(request)
    with store.transaction() as conn:
        # Serialize duplicate creation for the same tenant on PostgreSQL as well as SQLite.
        conn.execute(select(accounts.c.id).where(accounts.c.id == tenant).with_for_update())
        tombstone = conn.execute(
            select(entities.c.id).where(
                entities.c.tenant_id == tenant,
                entities.c.kind == "record",
                entities.c.client_id == str(body.client_record_id),
                entities.c.deleted.is_(True),
            )
        ).first()
        if tombstone:
            raise HTTPException(410, "record_previously_deleted")
        existing = store.list(conn, tenant, "record", client_id=str(body.client_record_id))
        if existing:
            if existing[0]["data"]["original_text"] != body.text:
                raise HTTPException(409, "idempotency_payload_mismatch")
            return record_detail(store, conn, existing[0])
        row = store.add(
            conn,
            tenant,
            "record",
            {
                "text": body.text,
                "original_text": body.text,
                "save": "stored",
                "processing": "queued",
                "identity": "unassigned",
                "facts": "proposed",
                "source_type": "text",
                "error_code": None,
            },
            client_id=str(body.client_record_id),
        )
        store.enqueue(conn, row)
        return record_detail(store, conn, row)


@router.get("")
def records(request: Request, q: str = "", tenant=Depends(principal)):
    store = store_for(request)
    with store.transaction() as conn:
        # Alpha keyword history fallback over encrypted records; no external embedding service.
        return [
            r
            for r in store.list(conn, tenant, "record")
            if q[:200].casefold() in r["data"]["text"].casefold()
        ]


@router.get("/{record_id}")
def detail(record_id: str, request: Request, tenant=Depends(principal)):
    store = store_for(request)
    with store.transaction() as conn:
        return record_detail(store, conn, store.get(conn, tenant, record_id, "record"))


@router.patch("/{record_id}")
def edit(record_id: str, body: RecordEdit, request: Request, tenant=Depends(principal)):
    store = store_for(request)
    with store.transaction() as conn:
        row = store.get(conn, tenant, record_id, "record", lock=True)
        if row["version"] != body.expected_version:
            raise Conflict()
        invalidate_facts(store, conn, row)
        data = {
            **row["data"],
            "text": body.text,
            "asr_status": "manual",
            "processing": "queued",
            "facts": "proposed",
            "person_names": [],
            "error_code": None,
        }
        row = store.change(conn, row, data, body.expected_version, revision=row["revision"] + 1)
        store.enqueue(conn, row)
        return record_detail(store, conn, row)


@router.post("/{record_id}/resolution")
def resolve(record_id: str, body: Resolution, request: Request, tenant=Depends(principal)):
    store = store_for(request)
    with store.transaction() as conn:
        row = store.get(conn, tenant, record_id, "record", lock=True)
        customer_id = str(body.customer_id) if body.customer_id else None
        if customer_id:
            store.get(conn, tenant, customer_id, "customer")
        if row["version"] != body.expected_version:
            raise Conflict()
        if customer_id and len(row["data"].get("person_names", [])) > 1:
            raise HTTPException(409, "multiple_people_assign_segments")
        # Moving/unlinking resets explicit confirmations; candidates may be confirmed again.
        for fact in store.list(conn, tenant, "fact", source_id=record_id):
            if fact["data"]["state"] != "retracted":
                store.change(
                    conn,
                    fact,
                    {**fact["data"], "state": "proposed"},
                    fact["version"],
                    related_id=customer_id,
                )
        row = store.change(
            conn,
            row,
            {
                **row["data"],
                "identity": "linked" if customer_id else "unassigned",
                "facts": "proposed",
            },
            body.expected_version,
            related_id=customer_id,
        )
        return record_detail(store, conn, row)


@router.post("/{record_id}/facts/confirm")
def confirm(record_id: str, body: FactConfirmation, request: Request, tenant=Depends(principal)):
    store = store_for(request)
    with store.transaction() as conn:
        row = store.get(conn, tenant, record_id, "record", lock=True)
        if row["version"] != body.expected_version:
            raise Conflict()
        selected = {str(x) for x in body.fact_ids}
        facts = store.list(conn, tenant, "fact", source_id=record_id)
        current = {
            f["id"]: f
            for f in facts
            if f["data"]["source_revision"] == row["revision"] and f["data"]["state"] != "retracted"
        }
        if not selected.issubset(current):
            raise HTTPException(409, "facts_not_current")
        if any(not current[fid]["related_id"] for fid in selected):
            raise HTTPException(409, "resolve_customer_first")
        for fid in selected:
            fact = current[fid]
            store.change(
                conn,
                fact,
                {**fact["data"], "state": "confirmed"},
                fact["version"],
                related_id=fact["related_id"],
            )
        row = store.change(
            conn,
            row,
            {**row["data"], "facts": "confirmed" if selected else row["data"]["facts"]},
            body.expected_version,
        )
        return record_detail(store, conn, row)


@router.post("/{record_id}/retry")
def retry(record_id: str, body: VersionInput, request: Request, tenant=Depends(principal)):
    store = store_for(request)
    with store.transaction() as conn:
        row = store.get(conn, tenant, record_id, "record", lock=True)
        if row["data"]["processing"] not in ("failed", "partial_success"):
            raise HTTPException(409, "record_not_failed")
        invalidate_facts(store, conn, row)
        row = store.change(
            conn,
            row,
            {**row["data"], "processing": "queued", "facts": "proposed", "error_code": None},
            body.expected_version,
            revision=row["revision"] + 1,
        )
        store.enqueue(conn, row)
        return row


@router.delete("/{record_id}")
def delete(record_id: str, body: VersionInput, request: Request, tenant=Depends(principal)):
    store = store_for(request)
    with store.transaction() as conn:
        row = store.get(conn, tenant, record_id, "record", lock=True)
        if row["version"] != body.expected_version:
            raise Conflict()
        invalidate_facts(store, conn, row)
        conn.execute(
            sql_delete(audio_blobs).where(
                audio_blobs.c.tenant_id == tenant, audio_blobs.c.record_id == record_id
            )
        )
        return store.change(
            conn,
            row,
            {"save": "deleted"},
            body.expected_version,
            revision=row["revision"] + 1,
            deleted=True,
        )


@router.post("/{record_id}/segments/resolution")
def resolve_segments(
    record_id: str, body: SegmentResolution, request: Request, tenant=Depends(principal)
):
    store = store_for(request)
    with store.transaction() as conn:
        row = store.get(conn, tenant, record_id, "record", lock=True)
        if row["version"] != body.expected_version:
            raise Conflict()
        customer_id = str(body.customer_id) if body.customer_id else None
        if customer_id:
            store.get(conn, tenant, customer_id, "customer")
        current = {
            f["id"]: f
            for f in store.list(conn, tenant, "fact", source_id=record_id)
            if f["data"]["state"] != "retracted" and f["data"]["source_revision"] == row["revision"]
        }
        selected = {str(fid) for fid in body.fact_ids}
        if not selected.issubset(current):
            raise HTTPException(409, "facts_not_current")
        for fid in selected:
            fact = current[fid]
            store.change(
                conn,
                fact,
                {**fact["data"], "state": "proposed"},
                fact["version"],
                related_id=customer_id,
            )
        row = store.change(
            conn,
            row,
            {**row["data"], "identity": "segments", "facts": "proposed"},
            body.expected_version,
            related_id=None,
        )
        return record_detail(store, conn, row)


@router.post("/{record_id}/facts/retract")
def retract(record_id: str, body: FactConfirmation, request: Request, tenant=Depends(principal)):
    store = store_for(request)
    with store.transaction() as conn:
        row = store.get(conn, tenant, record_id, "record", lock=True)
        if row["version"] != body.expected_version:
            raise Conflict()
        for fid in body.fact_ids:
            fact = store.get(conn, tenant, str(fid), "fact")
            if fact["source_id"] != record_id or fact["data"]["source_revision"] != row["revision"]:
                raise HTTPException(409, "facts_not_current")
            store.change(conn, fact, {**fact["data"], "state": "proposed"}, fact["version"])
        row = store.change(conn, row, {**row["data"], "facts": "proposed"}, body.expected_version)
        return record_detail(store, conn, row)
