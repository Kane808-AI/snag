"""In-process background job worker for the Snag bot.

The bot's Telegram loop stays responsive: handle_message only acknowledges and
enqueues, and this worker claims jobs from the SQLite queue and runs the
ingest -> analyze_note -> analyze_triage pipeline on a daemon thread inside
the same process. No new infrastructure.

- start()  boots the thread (called from bot.main())
- pump()   runs the same loop body synchronously on the calling thread, which
           is how the test suite drives the queue without threads
- stop()   signals the thread to exit and joins it

Job lifecycle is owned by db.py: pending -> processing -> done | failed.
"""

import threading
import time

import db

POLL_INTERVAL = 1.0
STALE_JOB_AGE = 3600  # seconds; longer than any single job should run


class Worker:
    """Claim jobs and hand each to process_job (the bot's pipeline runner)."""

    def __init__(self, process_job, poll_interval=POLL_INTERVAL, name="snag-worker"):
        self._process_job = process_job
        self._poll_interval = poll_interval
        self._name = name
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        """Start the background thread. Idempotent."""
        if self._thread and self._thread.is_alive():
            return self._thread
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name=self._name, daemon=True)
        self._thread.start()
        return self._thread

    def stop(self, timeout=5.0):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout)
        self._thread = None

    def pump(self, max_jobs=None):
        """Process pending jobs on the calling thread. Returns jobs processed.

        Mirrors what the thread loop does, minus the sleep, so tests can drive
        the full pipeline synchronously.
        """
        count = 0
        while max_jobs is None or count < max_jobs:
            job = db.claim_next_job(self._name)
            if job is None:
                break
            count += 1
            self._run_job(job)
        return count

    def _run(self):
        # A previous process may have died mid-job; reset its orphans so they
        # get retried instead of sitting in 'processing' forever.
        db.requeue_stale_jobs(max_age_seconds=STALE_JOB_AGE)
        while not self._stop.is_set():
            job = db.claim_next_job(self._name)
            if job is None:
                self._stop.wait(self._poll_interval)
                continue
            try:
                self._run_job(job)
            except Exception as e:
                # _run_job already records failures; this guards the claim path.
                print("worker error:", repr(e), flush=True)

    def _run_job(self, job):
        try:
            self._process_job(job)
            db.complete_job(job["id"])
        except Exception as e:
            print(f"job {job['id']} failed: {repr(e)}", flush=True)
            db.fail_job(job["id"], repr(e))
