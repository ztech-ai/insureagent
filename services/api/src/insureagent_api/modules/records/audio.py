import base64
import hashlib
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from insureagent_ai.asr.local import MAX_AUDIO_BYTES, validate_wav
from insureagent_persistence.audio import load_audio
from insureagent_persistence.store import accounts, audio_blobs, entities
from sqlalchemy import insert, select

from insureagent_api.modules.identity.auth import principal, store_for

router = APIRouter(prefix="/v1/records", tags=["audio"])


@router.post("/audio", status_code=201)
async def upload(request: Request, client_record_id: UUID, tenant=Depends(principal)):
    # Stream directly to bounded memory, never spool plaintext uploads onto server disk.
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > MAX_AUDIO_BYTES:
            raise HTTPException(413, "audio_too_large")
    try:
        seconds = validate_wav(bytes(raw))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    digest = hashlib.sha256(raw).hexdigest()
    store = store_for(request)
    with store.transaction() as conn:
        conn.execute(select(accounts.c.id).where(accounts.c.id == tenant).with_for_update())
        previous = (
            conn.execute(
                select(entities).where(
                    entities.c.tenant_id == tenant,
                    entities.c.kind == "record",
                    entities.c.client_id == str(client_record_id),
                )
            )
            .mappings()
            .first()
        )
        if previous:
            if previous["deleted"]:
                raise HTTPException(410, "record_previously_deleted")
            row = store.unpack(previous)
            if row["data"].get("audio_sha256") != digest:
                raise HTTPException(409, "idempotency_payload_mismatch")
            return row
        row = store.add(
            conn,
            tenant,
            "record",
            {
                "text": "",
                "original_text": "",
                "save": "stored",
                "processing": "queued",
                "identity": "unassigned",
                "facts": "proposed",
                "source_type": "audio",
                "audio_sha256": digest,
                "audio_seconds": seconds,
                "asr_status": "queued",
                "error_code": None,
            },
            client_id=str(client_record_id),
        )
        conn.execute(
            insert(audio_blobs).values(
                tenant_id=tenant,
                record_id=row["id"],
                payload=store.seal(
                    tenant, "audio", row["id"], {"wav": base64.b64encode(raw).decode()}
                ),
            )
        )
        store.enqueue(conn, row)
        return row


@router.get("/{record_id}/audio")
def download(record_id: str, request: Request, tenant=Depends(principal)):
    store = store_for(request)
    with store.transaction() as conn:
        raw = load_audio(store, conn, tenant, record_id)
    return Response(
        raw,
        media_type="audio/wav",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": 'attachment; filename="recording.wav"',
        },
    )
