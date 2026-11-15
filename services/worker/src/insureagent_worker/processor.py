from datetime import datetime, timedelta, timezone

from insureagent_ai.asr.local import transcribe
from insureagent_ai.extraction.local import extract
from insureagent_persistence.audio import load_audio
from insureagent_persistence.store import Missing, jobs, now
from sqlalchemy import or_, select, update


class Processor:
    def __init__(self, store, extractor=extract, transcriber=transcribe):
        self.store = store
        self.extractor = extractor
        self.transcriber = transcriber

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
            return {
                **job,
                "text": record["data"]["text"],
                "source_type": record["data"].get("source_type", "text"),
            }

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
                code = error if isinstance(error, str) else "extraction_failed"
                partial = record["data"].get("asr_status") == "succeeded"
                data = {
                    **record["data"],
                    "processing": "partial_success" if partial else "failed",
                    "error_code": code,
                }
                self.store.change(conn, record, data, record["version"])
                self.finish(conn, job, "failed", code)
                return False
            self.store.settle_stage(conn, record, "extraction", len(record["data"]["text"]))
            for candidate in output["candidates"]:
                self.store.add(
                    conn,
                    job["tenant_id"],
                    "fact",
                    {**candidate, "state": "proposed", "source_revision": record["revision"]},
                    source_id=record["id"],
                    related_id=record["related_id"] if len(output["person_names"]) <= 1 else None,
                )
            data = {
                **record["data"],
                "identity": "unassigned"
                if len(output["person_names"]) > 1
                else record["data"]["identity"],
                "person_names": output["person_names"],
                "redacted_text": output["redacted_text"],
                "processor": output["processor"],
                "processing": "succeeded",
                "error_code": None,
            }
            self.store.change(
                conn,
                record,
                data,
                record["version"],
                related_id=None if len(output["person_names"]) > 1 else record["related_id"],
            )
            self.finish(conn, job, "succeeded")
            return True

    def checkpoint(self, job, transcript=None):
        """Renew the lease and optionally commit ASR before extraction, with the same fence."""
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
            if (
                current["fence"] != job["fence"]
                or current["state"] != "running"
                or current["lease_until"] < now()
            ):
                return False
            try:
                record = self.store.get(
                    conn, job["tenant_id"], job["record_id"], "record", lock=True
                )
            except Missing:
                return False
            if record["revision"] != job["revision"]:
                return False
            conn.execute(
                update(jobs)
                .where(
                    jobs.c.tenant_id == job["tenant_id"],
                    jobs.c.id == job["id"],
                    jobs.c.fence == job["fence"],
                )
                .values(
                    lease_until=(datetime.now(timezone.utc) + timedelta(seconds=90)).isoformat()
                )
            )
            if transcript is not None:
                self.store.settle_stage(
                    conn, record, "asr", round(record["data"].get("audio_seconds", 0))
                )
                self.store.change(
                    conn,
                    record,
                    {
                        **record["data"],
                        "text": transcript,
                        "asr_status": "succeeded",
                        "asr_engine": "vosk-local",
                    },
                    record["version"],
                )
            return True

    def run_once(self):
        job = self.claim()
        if job is None:
            return False
        if job.get("skip"):
            return True
        if job["source_type"] == "audio" and not job["text"]:
            try:
                with self.store.transaction() as conn:
                    audio = load_audio(self.store, conn, job["tenant_id"], job["record_id"])
                transcript = self.transcriber(audio, lambda: self.checkpoint(job))
                if not isinstance(transcript, str) or not 1 <= len(transcript) <= 20000:
                    raise ValueError("invalid_transcript")
                if not self.checkpoint(job, transcript):
                    return True
                job["text"] = transcript
            except Exception:
                self.deliver(job, error="asr_unavailable")
                return True
        try:
            output = self.extractor(job["text"])
            if not isinstance(output.get("person_names"), list) or len(output["candidates"]) > 100:
                raise ValueError("invalid_output")
            for candidate in output["candidates"]:
                start, end = candidate["start"], candidate["end"]
                if not 0 <= start < end <= len(job["text"]):
                    raise ValueError("invalid_evidence_range")
                if job["text"][start:end] != candidate["evidence"]:
                    raise ValueError("invalid_evidence")
        except Exception:
            self.deliver(job, error=True)
        else:
            self.deliver(job, output=output)
        return True
