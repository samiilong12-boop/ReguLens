# ADR 0006: PostgreSQL-Backed Asynchronous Jobs without Distributed Queues

## Status
Approved (Architecture Decision for Phase 0B / Phase 1)

## Date
2026-11-07

## Context
ReguLens requires background execution for a small set of non-blocking tasks:
1. Parsing uploaded PDF documents and extracting text.
2. Invoking the server-side AI extraction adapter.
3. Generating downloadable, versioned PDF compliance research reports.
4. Periodically checking regulatory source freshness and metadata sync.

The original specification (`docs/SPEC_MODULES.md`) proposed deploying Redis and Celery. However, `AGENTS.md` Rule 15 and `.agents/rules/QUALITY_GATES.md` Section 5 mandate minimal technology:
> "Start from: a web app, a backend API, PostgreSQL, private file storage. Do not add Redis, Celery or another queue, pgvector or semantic search, or separate services unless you show a real need for the approved scope."

For the Vertical Slice (evaluating an orange export consignment involving 4–6 documents and occasional PDF report exports), a distributed queue infrastructure introduces severe unnecessary overhead (separate Redis container, broker connection pooling, distributed retry handling, process monitoring).

## Options Considered

### Option 1: Synchronous In-Request Processing
- Execute PDF parsing and report generation directly in the HTTP request thread.
- *Pros:* Zero queue mechanism.
- *Cons:* PDF extraction and LLM calls can take 3–10 seconds. HTTP clients may timeout, and UI threads would hang, creating poor user experience and potential DOS under multiple simultaneous requests.

### Option 2: Redis + Celery / RQ
- Standard Python background job stack.
- *Pros:* Mature ecosystem.
- *Cons:* Requires running and securing a Redis server. Redis lacks transactional coordination with PostgreSQL (e.g. if the PostgreSQL transaction rolls back, the Redis message may have already been dispatched, leading to orphaned tasks). Adds deployment and monitoring complexity.

### Option 3: PostgreSQL Transactional Queue Table (`SKIP LOCKED`) with In-Process Async Worker (Approved)
- Use a dedicated table `background_jobs` in PostgreSQL.
- Jobs are enqueued inside the same database transaction that records the document upload or report request.
- A lightweight async worker loop running within the FastAPI process polls the table using `SELECT ... FOR UPDATE SKIP LOCKED`.
- Supports retries, exponential backoff, dead-letter recording, and job status polling (`QUEUED`, `PROCESSING`, `COMPLETED`, `FAILED`).

## Decision
Adopt **Option 3 (PostgreSQL Transactional Queue Table with `SKIP LOCKED`)**:

### 1. The `background_jobs` Table Schema
```sql
CREATE TABLE background_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    job_type VARCHAR(64) NOT NULL, -- 'DOCUMENT_PARSE', 'EVIDENCE_EXTRACT', 'REPORT_GENERATE'
    payload JSONB NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'QUEUED', -- 'QUEUED', 'PROCESSING', 'COMPLETED', 'FAILED'
    attempts INT NOT NULL DEFAULT 0,
    max_attempts INT NOT NULL DEFAULT 3,
    run_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    locked_at TIMESTAMPTZ,
    locked_by VARCHAR(128),
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_background_jobs_polling 
ON background_jobs (status, run_at) 
WHERE status = 'QUEUED';
```

### 2. Job Consumption Pattern
The worker loop queries for ready jobs atomically:
```sql
WITH next_job AS (
    SELECT id
    FROM background_jobs
    WHERE status = 'QUEUED' 
      AND run_at <= CURRENT_TIMESTAMP
    ORDER BY run_at ASC
    LIMIT 1
    FOR UPDATE SKIP LOCKED
)
UPDATE background_jobs
SET status = 'PROCESSING',
    locked_at = CURRENT_TIMESTAMP,
    locked_by = :worker_id,
    attempts = attempts + 1,
    updated_at = CURRENT_TIMESTAMP
FROM next_job
WHERE background_jobs.id = next_job.id
RETURNING background_jobs.*;
```

### 3. Execution Lifecycle
- **Atomicity:** When an exporter uploads a document, the document row and the `DOCUMENT_PARSE` job row are inserted within the exact same database transaction. If the upload transaction fails, no phantom job exists.
- **Worker Runtime:** In the Vertical Slice, the worker runs as an `asyncio.Task` background loop inside the FastAPI application process.
- **Failure and Retries:** If a job fails (e.g. transient AI timeout), the worker increments `attempts`, sets `run_at = CURRENT_TIMESTAMP + (attempts * 30 seconds)`, and resets status to `QUEUED`. If `attempts >= max_attempts`, status is set to `FAILED` with `error_message` preserved for audit.

## Consequences
- **Positive:**
  - Zero extra infrastructure (no Redis, no RabbitMQ).
  - Perfect ACID transactional guarantees between application data and background jobs.
  - Zero phantom jobs on transaction rollbacks.
  - Trivial to inspect and debug directly in PostgreSQL (`SELECT * FROM background_jobs`).
- **Negative / Trade-offs:**
  - High polling frequency could slightly increase database queries if not tuned (using 2-second sleep when idle).
  - Not designed for millions of jobs per second (which is completely unnecessary for the B2B export workflow in Phase 2).

## Reversal Path
If task volume grows dramatically in Phase 3 or 4, the queue consumer interface (`JobQueue.enqueue()`) can be swapped to Celery, Temporal, or SQS without touching domain business logic.
