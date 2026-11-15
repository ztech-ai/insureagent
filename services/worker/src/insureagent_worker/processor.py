from datetime import datetime, timedelta, timezone

from insureagent_ai.extraction.local import extract
from insureagent_persistence.store import Missing, jobs, now
from sqlalchemy import or_, select, update


class Processor:
    def __init__(self, store, extractor=extract):
        self.store = store
        self.extractor = extractor

    def claim(self):
        with self.store.transaction() as conn:
            eligible = or_(
                jobs.c.state == "queued", (jobs.c.state == "running") & (jobs.c.lease_until < now())
            )
            query = select(jobs).where(eligible).order_by(jobs.c.id).limit(1)
            if self.store.engine.dialect.name == "postgresql":
                query = query.with_for_update(skip_locked=True)
            job = conn.execute(query).mappings().first()
            if job is None:
                return None
            job = dict(job)
            result = conn.execute(
                update(jobs)
                .where(
                    jobs.c.tenant_id == job["tenant_id"],
                    jobs.c.id == job["id"],
                    jobs.c.fence == job["fence"],
                    eligible,
                )
                .values(
                    state="running",
                    fence=job["fence"] + 1,
                    attempts=job["attempts"] + 1,
                    lease_until=(datetime.now(timezone.utc) + timedelta(seconds=90)).isoformat(),
                )
            )
            if result.rowcount != 1:
                return None
            job["fence"] += 1
            try:
                record = self.store.get(conn, job["tenant_id"], job["record_id"], "record")
            except Missing:
                self.finish(conn, job, "cancelled")
                return {**job, "skip": True}
            if record["revision"] != job["revision"]:
                self.finish(conn, job, "cancelled")
                return {**job, "skip": True}
            return {**job, "text": record["data"]["text"]}

    def finish(self, conn, job, state, error=None):
        conn.execute(
            update(jobs)
            .where(
                jobs.c.tenant_id == job["tenant_id"],
                jobs.c.id == job["id"],
                jobs.c.fence == job["fence"],
            )
            .values(state=state, error_code=error, lease_until=None)
        )

    def deliver(self, job, output=None, error=None):
        with self.store.transaction() as conn:
            current = (
                conn.execute(
                    select(jobs)
                    .where(jobs.c.tenant_id == job["tenant_id"], jobs.c.id == job["id"])
                    .with_for_update()
                )
                .mappings()
                .first()
            )
            if current["state"] != "running" or current["fence"] != job["fence"]:
                return False
            if current["lease_until"] < now():
                return False
            try:
                record = self.store.get(
                    conn, job["tenant_id"], job["record_id"], "record", lock=True
                )
            except Missing:
                self.finish(conn, job, "cancelled")
                return False
            if record["revision"] != job["revision"]:
                self.finish(conn, job, "cancelled")
                return False
            if error:
                data = {**record["data"], "processing": "failed", "error_code": "extraction_failed"}
                self.store.change(conn, record, data, record["version"])
                self.finish(conn, job, "failed", "extraction_failed")
                return False
            for candidate in output["candidates"]:
                self.store.add(
                    conn,
                    job["tenant_id"],
                    "fact",
                    {**candidate, "state": "proposed", "source_revision": record["revision"]},
                    source_id=record["id"],
                    related_id=record["related_id"],
                )
            data = {
                **record["data"],
                "person_names": output["person_names"],
                "redacted_text": output["redacted_text"],
                "processor": output["processor"],
                "processing": "succeeded",
                "error_code": None,
            }
            self.store.change(conn, record, data, record["version"])
            self.finish(conn, job, "succeeded")
            return True

    def run_once(self):
        job = self.claim()
        if job is None:
            return False
        if job.get("skip"):
            return True
        try:
            output = self.extractor(job["text"])
        except Exception:
            self.deliver(job, error=True)
        else:
            self.deliver(job, output=output)
        return True
