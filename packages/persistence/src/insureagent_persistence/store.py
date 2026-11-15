import base64
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import (
    Boolean,
    Column,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    create_engine,
    event,
    insert,
    select,
    update,
)

metadata = MetaData()
accounts = Table(
    "accounts",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("username", String(100), unique=True, nullable=False),
    Column("password_hash", String(256), nullable=False),
)
sessions = Table(
    "sessions",
    metadata,
    Column("token_hash", String(64), primary_key=True),
    Column("tenant_id", String(36), nullable=False),
    Column("expires_at", String(40), nullable=False),
    ForeignKeyConstraint(["tenant_id"], ["accounts.id"]),
)
entities = Table(
    "entities",
    metadata,
    Column("tenant_id", String(36), primary_key=True),
    Column("id", String(36), primary_key=True),
    Column("kind", String(24), nullable=False, index=True),
    Column("version", Integer, nullable=False, default=1),
    Column("revision", Integer, nullable=False, default=1),
    Column("deleted", Boolean, nullable=False, default=False),
    Column("client_id", String(36), nullable=True),
    Column("related_id", String(36), nullable=True),
    Column("source_id", String(36), nullable=True),
    Column("created_at", String(40), nullable=False),
    Column("payload", LargeBinary, nullable=False),
    ForeignKeyConstraint(["tenant_id"], ["accounts.id"]),
    ForeignKeyConstraint(["tenant_id", "related_id"], ["entities.tenant_id", "entities.id"]),
    ForeignKeyConstraint(["tenant_id", "source_id"], ["entities.tenant_id", "entities.id"]),
    UniqueConstraint("tenant_id", "kind", "client_id"),
)
jobs = Table(
    "jobs",
    metadata,
    Column("tenant_id", String(36), primary_key=True),
    Column("id", String(36), primary_key=True),
    Column("record_id", String(36), nullable=False),
    Column("revision", Integer, nullable=False),
    Column("state", String(24), nullable=False),
    Column("fence", Integer, nullable=False, default=0),
    Column("lease_until", String(40), nullable=True),
    Column("attempts", Integer, nullable=False, default=0),
    Column("error_code", String(40), nullable=True),
    ForeignKeyConstraint(["tenant_id", "record_id"], ["entities.tenant_id", "entities.id"]),
    UniqueConstraint("tenant_id", "record_id", "revision"),
)
outbox = Table(
    "outbox",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("tenant_id", String(36), nullable=False),
    Column("job_id", String(36), nullable=False),
    Column("created_at", String(40), nullable=False),
    ForeignKeyConstraint(["tenant_id", "job_id"], ["jobs.tenant_id", "jobs.id"]),
)


audio_blobs = Table(
    "audio_blobs",
    metadata,
    Column("tenant_id", String(36), primary_key=True),
    Column("record_id", String(36), primary_key=True),
    Column("payload", LargeBinary, nullable=False),
    ForeignKeyConstraint(["tenant_id", "record_id"], ["entities.tenant_id", "entities.id"]),
)


schema_versions = Table(
    "schema_versions",
    metadata,
    Column("version", Integer, primary_key=True),
    Column("installed_at", String(40), nullable=False),
)
stage_usage = Table(
    "stage_usage",
    metadata,
    Column("tenant_id", String(36), primary_key=True),
    Column("record_id", String(36), primary_key=True),
    Column("revision", Integer, primary_key=True),
    Column("stage", String(24), primary_key=True),
    Column("units", Integer, nullable=False),
    Column("completed_at", String(40), nullable=False),
    ForeignKeyConstraint(["tenant_id", "record_id"], ["entities.tenant_id", "entities.id"]),
)
Index("ix_entities_tenant_kind_time", entities.c.tenant_id, entities.c.kind, entities.c.created_at)
Index("ix_jobs_claim", jobs.c.state, jobs.c.lease_until)


def now():
    return datetime.now(timezone.utc).isoformat()


class Conflict(Exception):
    pass


class Missing(Exception):
    pass


class Store:
    def __init__(self, url: str, key: str):
        raw = base64.b64decode(key, validate=True)
        if len(raw) != 32:
            raise ValueError("ALPHA_DATA_KEY must contain 32 base64-encoded bytes")
        self.cipher = AESGCM(raw)
        self.engine = create_engine(url, pool_pre_ping=True)
        if url.startswith("sqlite"):

            @event.listens_for(self.engine, "connect")
            def sqlite_settings(dbapi, _):
                dbapi.execute("PRAGMA foreign_keys=ON")
                dbapi.execute("PRAGMA busy_timeout=10000")

    def initialize(self):
        # Initial Alpha schema only; explicit operator action, never implicit on API boot.
        metadata.create_all(self.engine)
        with self.transaction() as conn:
            versions = list(conn.execute(select(schema_versions.c.version)).scalars())
            if any(v != 1 for v in versions):
                raise ValueError("unsupported_schema_version")
            if not versions:
                conn.execute(insert(schema_versions).values(version=1, installed_at=now()))

    @contextmanager
    def transaction(self):
        with self.engine.connect() as conn:
            if self.engine.dialect.name == "sqlite":
                conn.exec_driver_sql("BEGIN IMMEDIATE")
            else:
                conn.begin()
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def seal(self, tenant, kind, ident, value):
        nonce = os.urandom(12)
        aad = f"{tenant}/{kind}/{ident}".encode()
        return nonce + self.cipher.encrypt(
            nonce, json.dumps(value, ensure_ascii=False).encode(), aad
        )

    def unpack(self, row):
        value = dict(row)
        ciphertext = value.pop("payload")
        aad = f"{value['tenant_id']}/{value['kind']}/{value['id']}".encode()
        value["data"] = json.loads(self.cipher.decrypt(ciphertext[:12], ciphertext[12:], aad))
        return value

    def get(self, conn, tenant, ident, kind, *, lock=False):
        query = select(entities).where(
            entities.c.tenant_id == tenant,
            entities.c.id == ident,
            entities.c.kind == kind,
            entities.c.deleted.is_(False),
        )
        if lock:
            query = query.with_for_update()
        row = conn.execute(query).mappings().first()
        if row is None:
            raise Missing()
        return self.unpack(row)

    def list(self, conn, tenant, kind, **filters):
        query = select(entities).where(
            entities.c.tenant_id == tenant, entities.c.kind == kind, entities.c.deleted.is_(False)
        )
        for name, value in filters.items():
            query = query.where(entities.c[name] == value)
        return [
            self.unpack(row)
            for row in conn.execute(query.order_by(entities.c.created_at.desc())).mappings()
        ]

    def add(self, conn, tenant, kind, data, **columns):
        ident = str(uuid4())
        conn.execute(
            insert(entities).values(
                tenant_id=tenant,
                id=ident,
                kind=kind,
                version=1,
                revision=1,
                deleted=False,
                created_at=now(),
                payload=self.seal(tenant, kind, ident, data),
                **columns,
            )
        )
        return self.get(conn, tenant, ident, kind)

    def change(self, conn, row, data, expected_version, **columns):
        if row["version"] != expected_version:
            raise Conflict()
        result = conn.execute(
            update(entities)
            .where(
                entities.c.tenant_id == row["tenant_id"],
                entities.c.id == row["id"],
                entities.c.version == expected_version,
                entities.c.deleted.is_(False),
            )
            .values(
                payload=self.seal(row["tenant_id"], row["kind"], row["id"], data),
                version=expected_version + 1,
                **columns,
            )
        )
        if result.rowcount != 1:
            raise Conflict()
        if columns.get("deleted"):
            return {"id": row["id"], "deleted": True, "version": expected_version + 1}
        return self.get(conn, row["tenant_id"], row["id"], row["kind"])

    def enqueue(self, conn, record):
        ident = str(uuid4())
        conn.execute(
            insert(jobs).values(
                tenant_id=record["tenant_id"],
                id=ident,
                record_id=record["id"],
                revision=record["revision"],
                state="queued",
                fence=0,
                attempts=0,
            )
        )
        conn.execute(
            insert(outbox).values(
                id=str(uuid4()), tenant_id=record["tenant_id"], job_id=ident, created_at=now()
            )
        )
        return ident

    def settle_stage(self, conn, record, stage, units):
        key = dict(
            tenant_id=record["tenant_id"],
            record_id=record["id"],
            revision=record["revision"],
            stage=stage,
        )
        query = select(stage_usage)
        for name, value in key.items():
            query = query.where(stage_usage.c[name] == value)
        if conn.execute(query).first() is None:
            conn.execute(insert(stage_usage).values(**key, units=units, completed_at=now()))
