# ReguLens — Privacy Policy (Draft)

> **Draft, requires qualified legal review.**  
> *In accordance with `AGENTS.md` Rule 14, this document is a preliminary operational draft prepared for software architecture planning. It does NOT constitute formal legal advice, an approved privacy notice, or an authoritative interpretation of law. It MUST be reviewed, customized, and approved by a qualified attorney licensed in Egypt and the European Union prior to publication or customer reliance.*

---

## 1. Introduction & Scope

ReguLens ("we", "us", or "our") operates a B2B Software-as-a-Service (SaaS) platform providing regulatory intelligence, document verification, and export-readiness assistance to manufacturers, agricultural producers, and exporters.

This Privacy Policy explains how we collect, process, store, transfer, and protect personal data when individuals access our website, create user accounts, or utilize our compliance software.

### Governing Legal Frameworks
This draft is designed to address the principles of:
1. **The European Union General Data Protection Regulation (EU) 2016/679 ("GDPR")**
2. **The Egyptian Personal Data Protection Law No. 151 of 2020 ("PDPL")**

---

## 2. Roles: Data Controller vs. Data Processor

Depending on the context of data processing, ReguLens acts in two distinct capacities:

### 2.1. ReguLens as a Data Controller
ReguLens acts as a Data Controller for:
- Account registration information (names, corporate email addresses, passwords, phone numbers).
- Customer relationship management, billing contacts, and contract execution.
- Security event logs and platform usage telemetry.

### 2.2. ReguLens as a Data Processor
ReguLens acts as a Data Processor on behalf of our B2B customers (the "Exporter" or "Tenant") for:
- Data contained within uploaded commercial export documents (such as exporter and consignee names, authorized signatory signatures, CapQ phytosanitary inspector names, laboratory technician signatures, and customs broker details).
- The customer remains the Data Controller for all customer-uploaded business and trade documents.

---

## 3. Categories of Personal Data Collected

1. **Identity & Account Information:** Full name, corporate email address, employer/company name, job title, encrypted password hash.
2. **Technical & Telemetry Data:** IP addresses, browser user-agent strings, device metadata, session timestamps, and page request routes.
3. **Documentary Data (Processor Context):** Names, job titles, and official credentials of inspectors, analysts, and export agents appearing on uploaded PDF certificates and laboratory reports.
4. **Audit Trail Data:** Records of user actions (document uploads, review decisions, report downloads).

*Special Category Data:* ReguLens does NOT knowingly collect or process sensitive/special category personal data (biometric data, racial or ethnic origin, political opinions, health data).

---

## 4. Lawful Bases for Processing (GDPR Art. 6 & Egyptian Law 151/2020 Art. 2)

| Purpose of Processing | Lawful Basis (GDPR) | Legal Basis (Egyptian Law 151/2020) |
|---|---|---|
| Creating and managing user accounts | **Contractual Necessity** (Art. 6(1)(b)) | Contract execution / Consent |
| Providing document parsing and gap analysis | **Contractual Necessity** (Art. 6(1)(b)) | Performance of agreed SaaS services |
| Securing the platform and preventing abuse | **Legitimate Interests** (Art. 6(1)(f)) | Security and fraud prevention |
| Maintaining tamper-evident audit logs | **Legal Obligation** (Art. 6(1)(c)) & Legitimate Interests | Regulatory and commercial defense |

---

## 5. Sub-Processors & Data Sharing

We do not sell personal data. We engage vetted third-party infrastructure sub-processors strictly to deliver our core SaaS functionality:

| Sub-Processor | Service Provided | Location / Transfer Mechanism |
|---|---|---|
| **Managed Cloud Hosting** (e.g. Hetzner / AWS) | Compute servers and encrypted PostgreSQL databases | EU / Data Processing Agreement with Standard Contractual Clauses (SCCs) |
| **Object Storage Provider** (e.g. Cloudflare R2 / AWS S3) | Encrypted private file storage for uploaded documents | EU / SCCs |
| **AI Extraction Provider** (e.g. Google Gemini API / OpenAI API) | Server-side text-to-JSON document entity extraction (zero training on customer data) | EU/US / Data Processing Addendum; customer data not used for model training |

---

## 6. International Data Transfers

When personal data originating from Egypt or the European Union is transferred internationally (e.g., between Egyptian exporter workstations and EU cloud data centers):
1. **Under GDPR:** Transfers are governed by European Commission Standard Contractual Clauses (SCCs) or adequacy decisions.
2. **Under Egyptian Law 151/2020 (Articles 14–16):** Cross-border transfers of personal data require compliance with licensing and approval regulations issued by the Egyptian Personal Data Protection Center (PDPC). *Requires formal legal counsel review prior to commercial launch.*

---

## 7. Data Subject Rights

Subject to verification and applicable legal exceptions, individuals have the following rights:
1. **Right of Access:** Request a copy of personal data processed by ReguLens.
2. **Right to Rectification:** Request correction of inaccurate personal data.
3. **Right to Erasure ("Right to be Forgotten"):** Request deletion of personal account data when no longer needed.
4. **Right to Restriction of Processing:** Request restriction of processing under certain contested circumstances.
5. **Right to Data Portability:** Receive personal data in a structured, machine-readable format.
6. **Right to Object:** Object to processing based on legitimate interests.

To exercise these rights, users may contact: `privacy@regulens.com` *(placeholder; requires official corporate designation)*.

---

## 8. Security Measures

ReguLens implements state-of-the-art technical and organizational measures to safeguard personal data, including:
- TLS 1.3 encryption in transit.
- AES-256 encryption at rest for databases and file storage.
- Strict PostgreSQL Row Level Security (RLS) guaranteeing tenant isolation.
- Role-based access control (RBAC) and least privilege principles.
- Regular security audits and automated vulnerability scanning.

---

## 9. Contact & Qualified Legal Review Requirement

This policy must be submitted to qualified legal counsel specializing in Egyptian data protection law and European privacy law.

*Draft prepared for Phase 0B software architecture baseline.*
