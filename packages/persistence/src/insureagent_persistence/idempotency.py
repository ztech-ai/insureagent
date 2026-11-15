import hashlib
import json

from sqlalchemy import select

from insureagent_persistence.store import Conflict, accounts


def create_once(store, conn, tenant, kind, client_id, data, **columns):
    conn.execute(select(accounts.c.id).where(accounts.c.id == tenant).with_for_update())
    digest = hashlib.sha256(json.dumps([data, columns], sort_keys=True).encode()).hexdigest()
    if client_id:
        existing = store.list(conn, tenant, kind, client_id=str(client_id))
        if existing:
            if existing[0]["data"].get("_create_hash") != digest:
                raise Conflict()
            return existing[0]
    return store.add(
        conn,
        tenant,
        kind,
        {**data, "_create_hash": digest},
        client_id=str(client_id) if client_id else None,
        **columns,
    )
