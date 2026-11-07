# ReguLens — Data Retention & Deletion Policy

> **Draft, requires qualified legal review.**  
> *In accordance with `AGENTS.md` Rule 14, this document is an engineering and operational draft. It must be reviewed and formally approved by a qualified privacy attorney before commercial reliance or customer onboarding.*

---

## 1. Purpose & Scope

This Data Retention Policy governs the lifecycle of data collected, stored, processed, and deleted within the ReguLens multi-tenant SaaS platform. It establishes retention periods, customer offboarding protocols, and data minimization procedures in compliance with:
- General Data Protection Regulation (Regulation (EU) 2016/679 - GDPR)
- Egyptian Personal Data Protection Law (Law No. 151 of 2020)
- Applicable commercial recordkeeping standards

---

## 2. Data Inventory & Retention Classification

Data within ReguLens is categorized into six distinct classifications, each with defined retention and deletion rules:

| Category ID | Data Category | Description | Examples | Retention Period | Deletion / Purge Method |
|---|---|---|---|---|---|
| **CAT-01** | **User Account & Identity Data** | Personal data of registered users. | Name, email address, password hash, role, job title. | Duration of active customer subscription + **30 days** post-contract termination. | Hard delete from database; anonymized in audit records. |
| **CAT-02** | **Product & Operational Profiles** | Exporter product specifications. | Commercial name, HS code, variety, technical attributes. | Retained during active tenant subscription. Deleted **30 days** after tenant offboarding. | Cascading hard delete via `ON DELETE CASCADE`. |
| **CAT-03** | **Uploaded Export Documents** | Commercial and official trade files. | Phytosanitary certificates, lab reports, EUR.1 certs, commercial invoices. | Duration of tenant subscription, or configurable by tenant down to **90 days** post-export. | Secure cryptographic purge from private S3 object storage; associated metadata deleted from database. |
| **CAT-04** | **Extracted Evidence & Gap Analyses** | Structured data parsed from files. | Active substance mg/kg values, certificate numbers, issue dates. | Retained with the corresponding consignment. Deleted with parent consignment. | Hard delete from database. |
| **CAT-05** | **Generated Compliance Reports** | Compiled PDF export dossiers. | PDF reports, digital signatures, hash checksums. | Retained for **3 years** to satisfy commercial customs audit windows, unless tenant requests early deletion. | Purge from S3 storage and database upon tenant request or expiry. |
| **CAT-06** | **Security & Audit Logs** | Immutable system event records. | IP address, timestamp, user action, resource UUID, auth events. | **12 Months** from event timestamp. | Automated time-series pruning. Never editable; append-only during retention window. |
| **CAT-07** | **Regulatory Knowledge Base** | Public legal acts, citations, and rules. | EUR-Lex snapshots, CELEX numbers, official articles. | Permanent / Indefinite (historical legal archive). | Historical versions retained for retrospective audits. No personal data. |

---

## 3. Tenant Offboarding & Right to Erasure

### 3.1. Tenant Termination Workflow
When an organization terminates its ReguLens subscription:
1. **Grace Period (30 Days):** Tenant account is locked; export reports and dossiers remain accessible for download by the organization Owner.
2. **Automated Purge Execution (Day 31):**
   - Application initiates automated transactional purge job.
   - S3 objects under `tenants/{tenant_id}/*` are permanently deleted using AWS/R2 batch delete API.
   - Database executes `DELETE FROM tenants WHERE id = :tenant_id;`, triggering cascading deletions across all child tables (`products`, `consignments`, `documents`, `evidence_items`, `gap_analyses`, `export_reports`).
   - Confirmation certificate of data destruction is automatically generated and emailed to the tenant Owner.

### 3.2. Conflict Resolution: Erasure vs. Audit Log Integrity
Under GDPR Article 17(3)(b) (legal claims/obligations) and Law 151/2020, security audit logs may be retained for legitimate forensic defense:
- When a user exercises the right to erasure, their personal identity data in `users` is scrubbed and replaced with an anonymized pseudonym (e.g. `user_deleted_8f3a1...`).
- Historical audit records in `audit_logs` retain the action and timestamp but reference only the anonymized identifier, preserving log integrity while removing personal identifiers.

---

## 4. Backups & Disaster Recovery Retention
- Automated PostgreSQL database snapshots are retained for **14 days** in encrypted storage.
- S3 object storage versioning retains deleted object markers for **14 days** to guard against accidental deletion.
- Upon expiry of the backup retention window, purged tenant data is completely overwritten and unrecoverable across all backup media.
