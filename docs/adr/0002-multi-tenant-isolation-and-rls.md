# ADR 0002: Multi-Tenant Isolation via Defense-in-Depth (Composite Keys, Application Scoping, and PostgreSQL RLS)

## Status
Approved (Architecture Decision for Phase 1 / Phase 2)

## Date
2026-11-07

## Context
ReguLens serves multiple exporting businesses and trade organizations across both agriculture and apparel. Customers upload commercially sensitive trade documents, including confidential commercial invoices, packing lists, proprietary product specifications, laboratory test results with supplier details, and customs certificates.

Per `AGENTS.md` (Rule 7):
> "Tenant isolation and authorization are enforced on the backend and in the database, never only in the UI."

And per `.agents/rules/QUALITY_GATES.md` (Section 6):
> "Tenant-isolation tests exist for every table and endpoint that holds customer data. Every endpoint has an authorization test for each role, including negative cases."

A failure in tenant isolation could leak an exporter's commercial transactions, pricing, lab results, or buyer relationships to a competing exporter.

## Options Considered

### Option 1: Database-per-Tenant
- Each tenant receives a dedicated PostgreSQL database.
- *Pros:* Physical separation; zero risk of cross-tenant SQL leakage.
- *Cons:* Heavy operational overhead for database migrations, high connection pool overhead, expensive resource footprint, incompatible with minimal baseline.

### Option 2: Application-Layer Filtering Only (Single Database, Shared Tables)
- Every table includes a `tenant_id` column; API endpoints manually include `WHERE tenant_id = :current_tenant_id` in SQL queries.
- *Pros:* Simple to implement in code.
- *Cons:* Violates Rule 7 of `AGENTS.md`. A single developer omission, missing `WHERE` clause, or raw SQL bug exposes cross-tenant data. Completely unsafe for commercial compliance data.

### Option 3: Defense-in-Depth: Application Scoping + Composite Foreign Keys + PostgreSQL RLS (Approved)
- Every customer-owned table includes a foreign key `tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE`.
- Composite unique constraints `UNIQUE (tenant_id, id)` and composite foreign keys `FOREIGN KEY (tenant_id, parent_id) REFERENCES parent_table(tenant_id, id)` guarantee relationship integrity at the database schema level.
- The application layer (FastAPI dependency injection) extracts and cryptographically verifies the tenant context from the authenticated server-side session/JWT.
- The database connection sets a transaction-local session variable: `SELECT set_config('app.current_tenant_id', :tenant_id, true)`.
- PostgreSQL Row Level Security (RLS) is enabled and forced (`ENABLE ROW LEVEL SECURITY; FORCE ROW LEVEL SECURITY`) on ALL 12 customer-associated tables. Policies restrict `SELECT`, `INSERT`, `UPDATE`, and `DELETE` strictly to rows where `tenant_id = current_setting('app.current_tenant_id', true)::uuid`.
- High-privilege database migration roles (DDL) are strictly isolated from runtime application database roles (DML). Runtime role `regulens_app` has `NOBYPASSRLS`.

## Decision
Adopt **Option 3 (Defense-in-Depth: Application Scoping + Composite Foreign Keys + PostgreSQL RLS)**:

### 1. Accurate Boundary Definition
- **Important Note on Terminology:** PostgreSQL Row Level Security is an additional database-engine authorization boundary, **NOT cryptographic isolation**. RLS enforces declarative policy filters against a session variable. The security of the boundary depends on the server-side integrity of the authentication layer and the least-privilege configuration of the runtime role (`NOBYPASSRLS`).

### 2. Dual-Layer Enforcement & Relationship Integrity
1. **Layer 1 (Schema & Composite Integrity):**
   - Every tenant-owned child table contains `tenant_id` and references parent tables via composite foreign keys:
     `FOREIGN KEY (tenant_id, parent_id) REFERENCES parent_table(tenant_id, id)`.
   - This physically prevents Tenant A from referencing Tenant B's products, consignments, or documents at the database schema level, even if an application bug attempts to do so.
2. **Layer 2 (Application/ORM):**
   - FastAPI request middleware verifies the authenticated JWT and extracts `current_user.tenant_id`.
   - SQLAlchemy repositories automatically include `WHERE tenant_id = :tenant_id`.
3. **Layer 3 (Database Engine RLS):**
   - `ALTER TABLE ... FORCE ROW LEVEL SECURITY` applied to: `tenants`, `tenant_users`, `products`, `consignments`, `documents`, `evidence_items`, `gap_analyses`, `gap_analysis_items`, `human_reviews`, `export_reports`, `background_jobs`, and `audit_logs`.
   - Unprivileged runtime database role (`regulens_app`) operates with `NOBYPASSRLS`.
   - On `audit_logs`, `UPDATE` and `DELETE` are revoked from `regulens_app` to ensure an immutable append-only audit trail.

### 3. Transaction-Local Tenant Context & Connection Pooling
- When connection poolers (PgBouncer in transaction pooling mode) are used, global session variables can leak between pooled connections.
- Therefore, the tenant context is strictly set inside transaction blocks using transaction-local configuration:
  ```sql
  SELECT set_config('app.current_tenant_id', :tenant_id, true);
  ```
  The third parameter `true` scopes the variable strictly to the current transaction (`is_local = true`). When the transaction commits or rolls back, the variable is automatically reset to null.

### 4. Background Jobs & Worker Context Binding
- Asynchronous tasks executing from `background_jobs` claim a job row using `SELECT ... FOR UPDATE SKIP LOCKED`.
- Before executing any domain operation or querying tenant tables, the worker process begins a transaction and binds the job's `tenant_id`:
  ```python
  await db.execute(text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"), {"tenant_id": str(job.tenant_id)})
  ```
- This ensures background jobs execute under the exact same RLS boundaries as interactive user requests.

## Consequences
- **Positive:**
  - Absolute adherence to `AGENTS.md` Rule 7.
  - Zero accidental data leakage from missing ORM filters.
  - Relational schema enforces cross-tenant reference prevention via composite foreign keys.
  - Complete RLS coverage across all 12 customer tables.
- **Negative / Trade-offs:**
  - All migration scripts must define composite keys and RLS policies explicitly.
  - Integration tests must run against real PostgreSQL instances with unprivileged roles to verify RLS behavior.

## Reversal Path
Composite keys and RLS policies are standard PostgreSQL primitives and can be partitioned by `tenant_id` if high multi-tenant volume in Phase 4 requires table partitioning.
