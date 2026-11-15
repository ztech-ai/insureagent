import base64
import json

from sqlalchemy import select

from insureagent_persistence.store import Missing, audio_blobs


def load_audio(store, conn, tenant, record_id):
    store.get(conn, tenant, record_id, "record")
    row = conn.execute(
        select(audio_blobs.c.payload).where(
            audio_blobs.c.tenant_id == tenant, audio_blobs.c.record_id == record_id
        )
    ).first()
    if row is None:
        raise Missing()
    payload = row[0]
    value = json.loads(
        store.cipher.decrypt(payload[:12], payload[12:], f"{tenant}/audio/{record_id}".encode())
    )
    return base64.b64decode(value["wav"], validate=True)
