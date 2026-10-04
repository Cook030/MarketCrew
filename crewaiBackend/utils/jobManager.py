from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock


jobs_lock = Lock()
# ponytail: jobs live in one process; use durable storage when restart recovery is required.
jobs = {}


@dataclass
class Event:
    timestamp: datetime
    data: str


@dataclass
class Job:
    phase: str = 'Starting'
    status: str = 'STARTED'
    events: list = field(default_factory=list)
    result: object = None
    knowledge_base_id: str | None = None
    sources: list = field(default_factory=list)


def append_event(job_id, event_data):
    with jobs_lock:
        job = jobs.setdefault(job_id, Job())
        job.events.append(Event(datetime.now(timezone.utc), event_data))


def record_sources(job_id, passages):
    with jobs_lock:
        known = {source['chunk_id'] for source in jobs[job_id].sources}
        for passage in passages:
            if passage['chunk_id'] not in known:
                jobs[job_id].sources.append(passage)
                known.add(passage['chunk_id'])


def set_phase(job_id, phase):
    with jobs_lock:
        jobs[job_id].phase = phase
