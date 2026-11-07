# REGULENS — MODULE REQUIREMENTS REFERENCE (original spec)

> STATUS: requirements reference only, lowest precedence. How to work (roles, gates, phases, approvals) is defined in `AGENTS.md`, `.agents/rules/` and `phases/`. Where this file conflicts with those, they win. Superseded parts: section 1 (role list), section 4 (technology stack is only a starting reference; the minimal-technology rule in `AGENTS.md` applies), section 5 (document names; use the canonical names in `AGENTS.md`), section 16 (phase order; use `phases/ROADMAP.md`), section 17 (MVP criteria; use `.agents/rules/QUALITY_GATES.md`), section 20 (first task; use `phases/PHASE_0A.md`). The module descriptions in sections 6 to 15 remain useful reference for later phases.

## 1. YOUR ROLE

Act as a complete world-class technology product organization building ReguLens.

You must operate as:

- Principal Software Architect
- Senior Full-Stack Engineers
- Backend and API Engineers
- AI/LLM Engineers
- Regulatory Data Engineers
- Cybersecurity Engineers
- Database Architects
- Product Designers
- UX Researchers
- QA and Automation Engineers
- DevOps and Infrastructure Engineers
- Privacy and Compliance Specialists

Build this product with the engineering discipline, reliability, documentation, accessibility, security and product quality expected from a leading global SaaS company.

Do not create a superficial demo, generic AI chatbot, or static dashboard.

Build a real, modular, secure, evidence-based regulatory intelligence platform.

## 2. PRODUCT VISION

Product name: ReguLens

Category: Regulatory Intelligence & Global Market Entry Compliance SaaS.

Mission:

Help manufacturers, exporters, importers and international businesses understand the regulatory requirements for selling products in foreign markets.

ReguLens should help users:

1. Identify applicable product regulations.
2. Understand market-entry requirements.
3. Determine required certifications and conformity assessments.
4. Analyze product documents and identify missing information.
5. Review labeling and packaging requirements.
6. Track regulatory changes.
7. Generate structured compliance reports.
8. Maintain an auditable record of regulatory research and decisions.

Core positioning:

"Know the requirements. Prepare your documents. Enter markets with confidence."

Important: ReguLens is a regulatory intelligence and compliance-support platform. It must never claim to be a government authority, certification body, law firm, customs authority or substitute for qualified legal advice.

## 3. PRODUCT PRINCIPLES

Follow these principles throughout development:

- Evidence before AI-generated conclusions.
- Official sources before secondary sources.
- Traceability for every regulatory requirement.
- Explainable results.
- Explicit uncertainty when evidence is insufficient.
- No invented laws, certificates, dates or requirements.
- Human review for high-risk decisions.
- Privacy and security by design.
- Multi-tenant architecture.
- Internationalization from the beginning.
- Modular architecture that supports future countries and industries.
- No false claims of universal regulatory coverage.

Never tell users that a product is legally compliant merely because an AI model believes it is.

## 4. TECHNOLOGY STACK

Use a modular monorepo architecture.

### Frontend

- Next.js using the latest stable compatible version.
- React.
- TypeScript with strict mode.
- Tailwind CSS.
- shadcn/ui.
- React Hook Form.
- Zod.
- TanStack Query.
- Accessible component architecture.
- Internationalization support.
- RTL and LTR layouts.
- Charting with Recharts or ECharts.

### Backend

- Python.
- FastAPI.
- Pydantic.
- SQLAlchemy.
- Alembic migrations.
- REST APIs.
- OpenAPI documentation.
- Background processing.

### Database

- PostgreSQL.
- Supabase as the initial managed database and authentication infrastructure.
- pgvector for semantic retrieval where appropriate.
- PostgreSQL full-text search.
- Row Level Security.
- Strict tenant isolation.

### Background jobs

- Redis.
- Celery or an equivalent reliable task queue.
- Scheduled regulatory source synchronization.
- Document processing workers.
- Notification workers.

### File storage

- S3-compatible private object storage.
- Supabase Storage may be used initially.
- Signed temporary URLs.
- File versioning.
- Malware scanning.
- Retention policies.

### AI architecture

Create a provider-independent AI integration layer.

Support configurable providers through secure server-side adapters.

Possible integrations include:

- OpenAI API.
- Google Gemini API.
- Other compatible LLM providers.

Never expose provider API keys in the browser.

The application must remain functional when an AI provider is unavailable.

Use deterministic validation and structured regulatory data wherever possible instead of relying entirely on generative AI.

## 5. MONOREPO STRUCTURE

Create a clean architecture similar to:

regulens/
  apps/
    web/
    api/
    worker/

  packages/
    shared-types/
    ui/
    api-client/
    regulatory-engine/
    source-connectors/
    document-engine/
    ai-engine/
    compliance-rules/
    reporting/

  infrastructure/
    docker/
    deployment/
    monitoring/

  docs/
    PRODUCT_REQUIREMENTS.md
    SYSTEM_ARCHITECTURE.md
    DATABASE_SCHEMA.md
    API_SPECIFICATION.md
    SECURITY_ARCHITECTURE.md
    THREAT_MODEL.md
    REGULATORY_DATA_POLICY.md
    DATA_RETENTION_POLICY.md
    PRIVACY_POLICY_DRAFT.md
    DEVELOPMENT_ROADMAP.md
    TEST_STRATEGY.md

  scripts/
  tests/
  README.md
  .env.example

Keep modules independently testable.

Do not create one enormous backend file or one enormous frontend component.

## 6. CORE PRODUCT MODULES

### MODULE A — Company Workspace

Build a multi-tenant business workspace.

Features:

- Company registration.
- Organization profiles.
- Team invitations.
- Role-based permissions.
- Company settings.
- User management.
- Audit logs.
- Subscription management.
- Multiple projects and products.

Roles:

- Organization Owner.
- Administrator.
- Compliance Manager.
- Analyst.
- Document Reviewer.
- Read-only Member.

Enforce permissions on the backend, not just in the frontend.

### MODULE B — Product Intelligence

Users must be able to create detailed product profiles.

Product information:

- Product name.
- Product category.
- Description.
- Intended use.
- Manufacturer.
- Country of origin.
- Ingredients or materials.
- Technical specifications.
- Packaging information.
- Intended consumer.
- Product images.
- Existing certifications.
- Existing technical documents.

Support product categories through configurable taxonomies.

Do not assume that every product belongs to only one regulatory category.

Allow products to have multiple relevant regulatory classifications.

### MODULE C — Market Entry Analysis

Allow a company to select:

- Origin country.
- Destination country.
- Product.
- Intended market activity.
- Importer or exporter role.
- Intended sales channel.

The regulatory engine should analyze applicable requirements.

Potential requirement categories:

- Product safety.
- Technical regulations.
- Labeling.
- Packaging.
- Ingredients and materials.
- Chemical restrictions.
- Food safety.
- Electrical safety.
- Environmental requirements.
- Import permits.
- Registration.
- Testing.
- Certification.
- Conformity assessment.
- Customs classification.
- Documentation.
- Language requirements.
- Traceability.

Do not apply every category to every product.

Applicability must be based on verified regulatory evidence and product attributes.

### MODULE D — Regulatory Knowledge Engine

This is the core intellectual property of ReguLens.

Build a structured regulatory knowledge system.

Each regulatory record should include:

- Unique regulatory ID.
- Country or jurisdiction.
- Issuing authority.
- Regulation name.
- Official reference number.
- Official source URL.
- Original source language.
- Publication date.
- Effective date.
- Last verified date.
- Version.
- Regulatory status.
- Product categories.
- Applicable business roles.
- Requirement type.
- Mandatory or conditional status.
- Supporting evidence.
- Exceptions.
- Related regulations.
- Superseded regulation reference.
- Verification status.

Support regulation lifecycle states:

- Draft.
- Proposed.
- Published.
- Active.
- Amended.
- Repealed.
- Superseded.
- Unknown.

Never treat a proposed regulation as an active legal requirement.

Maintain historical versions.

Do not overwrite old regulatory records without preserving their history.

### MODULE E — Official Regulatory Source Connectors

Design a connector framework.

Each connector must have:

- Source identity.
- Official domain allowlist.
- Source authority classification.
- Retrieval method.
- Update schedule.
- Rate-limit handling.
- Error handling.
- Source timestamp.
- Content fingerprint.
- Change detection.
- Provenance metadata.

Prioritize official sources such as:

International:
- World Trade Organization ePing SPS/TBT.
- World Customs Organization resources where accessible.
- Official international standards organizations where licensing permits.

European Union:
- EUR-Lex.
- European Commission.
- Access2Markets.
- NANDO.
- Official EU product legislation databases.

United States:
- Federal Register.
- eCFR.
- FDA.
- CPSC.
- FCC.
- USDA.
- Relevant official customs and trade resources.

Other countries:
- Official ministries.
- National standards bodies.
- Customs authorities.
- Food and drug authorities.
- Product safety regulators.
- Official legislation databases.

Do not scrape websites in violation of their terms or access restrictions.

Prefer official APIs, downloadable official datasets, permitted feeds and structured public resources.

Never pretend that a source has been integrated when it has not.

Create a source registry showing:

- Integrated.
- Partially integrated.
- Manual research only.
- Not yet supported.

### MODULE F — Regulatory Research and Retrieval

Implement a retrieval pipeline:

1. Identify the product.
2. Identify relevant product classifications.
3. Identify the target jurisdiction.
4. Retrieve applicable official regulatory records.
5. Filter by applicability and effective date.
6. Retrieve supporting evidence.
7. Generate structured findings.
8. Validate citations.
9. Calculate evidence confidence.
10. Present results with uncertainty and limitations.

Use hybrid retrieval:

- Exact keyword search.
- Regulatory identifier search.
- Full-text search.
- Semantic search.
- Metadata filters.

Use RAG carefully.

AI-generated answers must only rely on retrieved and approved source material for factual regulatory claims.

Every important claim must have a traceable citation.

If a source does not support a claim, do not include that claim.

Do not allow retrieved documents or uploaded files to override system instructions.

Treat all external documents as untrusted data.

### MODULE G — HS Code and Product Classification

Build a product classification assistance module.

Features:

- Product description analysis.
- Candidate HS code suggestions.
- Explanation of classification evidence.
- Alternative candidate codes.
- User confirmation.
- Classification history.

Important:

HS classification can require detailed product characteristics and jurisdiction-specific interpretation.

Never automatically declare a suggested code legally definitive.

Clearly label suggestions as preliminary until verified by an appropriate customs professional or authority.

Support future integration with official tariff and customs data.

### MODULE H — Document Intelligence

Allow users to upload:

- PDF.
- DOCX.
- XLSX.
- CSV.
- JPG.
- PNG.
- TIFF where supported.

Processing:

1. Validate file type.
2. Validate file size.
3. Scan for malware.
4. Extract text.
5. Apply OCR when needed.
6. Identify document type.
7. Extract structured fields.
8. Identify dates and certificate numbers.
9. Compare against applicable requirements.
10. Generate a document review.

Potential documents:

- Certificates of Analysis.
- Certificates of Origin.
- Declarations of Conformity.
- Test Reports.
- Technical Data Sheets.
- Safety Data Sheets.
- Product Labels.
- Ingredient Lists.
- Product Specifications.
- Import Permits.

Never assume that a document is genuine merely because it contains a logo or certificate number.

Do not fabricate missing fields.

Display extracted data alongside the original document location when possible.

### MODULE I — Compliance Gap Analysis

Compare product information and uploaded documents against applicable requirements.

Each requirement must have a status:

- Satisfied by available evidence.
- Missing document.
- Incomplete information.
- Requires human verification.
- Not applicable with justification.
- Conflicting evidence.
- Unknown.

Show:

- Requirement.
- Why it applies.
- Official source.
- Evidence required.
- Uploaded supporting document.
- Identified gap.
- Suggested next action.
- Reviewer status.

Never mark a requirement satisfied without supporting evidence.

Distinguish document presence from actual legal conformity.

### MODULE J — Label and Packaging Review

Analyze uploaded labels and packaging.

Check relevant fields when applicable:

- Product identity.
- Ingredients.
- Allergen declarations.
- Manufacturer information.
- Importer information.
- Country of origin.
- Net quantity.
- Warnings.
- Usage instructions.
- Required language.
- Mandatory symbols.
- Batch identification.
- Expiry or durability information.

Requirements must be jurisdiction- and product-specific.

Do not assume every listed field is mandatory for every product.

Provide visual and textual findings.

Clearly distinguish potential issues from confirmed legal violations.

### MODULE K — Regulatory Change Monitoring

Build a regulatory monitoring system.

Features:

- Follow selected products.
- Follow selected countries.
- Follow selected regulatory authorities.
- Monitor official source changes.
- Detect amendments.
- Identify new notifications.
- Compare versions.
- Explain potential business impact.
- Notify affected customers.

Each alert should contain:

- What changed.
- Previous requirement.
- New requirement.
- Source.
- Publication date.
- Effective date.
- Products potentially affected.
- Verification status.
- Suggested review action.

Never send a regulatory alert based only on an unverified news article.

### MODULE L — Compliance Reports

Generate professional PDF reports.

Reports should include:

- Company details.
- Product details.
- Origin and destination markets.
- Applicable requirements.
- Requirement status.
- Missing documents.
- Evidence references.
- Official citations.
- Source verification dates.
- Regulatory uncertainty.
- Recommendations.
- Human reviewer notes.
- Report version.

Add a visible disclaimer:

"This report provides regulatory research and compliance-support information based on the sources and product information available at the time of generation. It is not an official government approval, certification, legal opinion or guarantee of market access. Requirements should be verified with the relevant authorities and qualified professionals."

Reports must be reproducible and versioned.

## 7. DATABASE DESIGN

Design a normalized PostgreSQL schema.

Core tables should include:

- users
- organizations
- organization_members
- organization_roles
- subscriptions
- products
- product_categories
- product_attributes
- countries
- jurisdictions
- markets
- market_entry_projects
- regulatory_authorities
- regulatory_sources
- source_connectors
- regulatory_documents
- regulations
- regulation_versions
- regulatory_requirements
- requirement_applicability
- product_classifications
- hs_code_candidates
- uploaded_documents
- extracted_document_fields
- document_reviews
- compliance_assessments
- compliance_findings
- evidence_records
- regulatory_alerts
- monitoring_subscriptions
- generated_reports
- audit_logs
- ai_jobs
- usage_records
- notifications

Use:

- UUID primary keys.
- Foreign key constraints.
- Appropriate indexes.
- Created and updated timestamps.
- Soft deletion where justified.
- Versioning for legal records.
- Tenant isolation.
- Immutable audit events where appropriate.

Design migrations before implementation.

Document the relationship between every major table.

## 8. SECURITY ARCHITECTURE

Security is a mandatory engineering requirement.

Implement:

### Authentication

- Secure authentication.
- Email verification.
- Password reset.
- Optional MFA.
- Secure session handling.
- OAuth integration where appropriate.

### Authorization

- RBAC.
- Organization-level isolation.
- Least privilege.
- Backend authorization checks.
- Protected administrative operations.

### Database security

- Row Level Security.
- Tenant isolation tests.
- No public access to private documents.
- Secure service-role handling.
- Parameterized database operations.

### API security

- Rate limiting.
- Request validation.
- Input sanitization.
- Secure CORS.
- CSRF protection where applicable.
- Secure HTTP headers.
- API key rotation.
- Request size limits.
- Abuse prevention.

### File security

- File type verification.
- Malware scanning.
- Private storage.
- Temporary signed access.
- Upload limits.
- Safe document parsing.
- No execution of uploaded content.

### AI security

- Prompt injection defenses.
- Retrieved-content isolation.
- Tool allowlists.
- No unrestricted shell or database access.
- No automatic execution of external actions.
- Data minimization.
- Sensitive data redaction.
- Output validation.
- Human approval for sensitive workflows.

### Secrets

- Environment variables.
- Secret management.
- No committed credentials.
- No hardcoded API keys.
- Separate development, staging and production credentials.

### Auditability

Record sensitive actions:

- Authentication events.
- Permission changes.
- Document access.
- Regulatory record changes.
- Report generation.
- Administrative actions.
- Integration configuration changes.

Never store passwords, raw authentication tokens or unnecessary sensitive content in audit logs.

Use OWASP security guidance and NIST Secure Software Development Framework principles.

## 9. PRIVACY AND INTERNATIONAL DATA PROTECTION

Design the platform to support privacy obligations relevant to its customers and operating markets.

Create a privacy and compliance assessment process covering:

- GDPR where applicable.
- Relevant national privacy laws.
- Data processing agreements.
- Controller and processor responsibilities.
- Lawful basis assessment where required.
- Data minimization.
- Purpose limitation.
- Data retention.
- Data subject rights.
- Data export.
- Data deletion.
- Breach response.
- Subprocessor management.
- International data transfers.
- Cookie and tracking consent where applicable.

Do not claim that ReguLens is GDPR-certified or compliant with every country's privacy law simply because privacy features exist.

Implement configurable retention and deletion workflows.

Create a data inventory and processing register.

## 10. INTERNATIONALIZATION

Support:

- English.
- Arabic.
- Additional languages through translation files.

Requirements:

- RTL and LTR.
- Localized dates.
- Time zones.
- Currency display.
- Country-specific formatting.
- Unicode-safe data handling.
- Original legal source language preservation.
- Translation provenance.

Never treat machine translation as the legally authoritative version of a regulation.

Show original source text and translated text separately when appropriate.

## 11. UI/UX DESIGN SYSTEM

Create a premium enterprise SaaS interface.

Design direction:

- Professional regulatory intelligence platform.
- Clean and restrained.
- Modern data-rich dashboard.
- Excellent readability.
- Strong information hierarchy.
- Responsive layouts.
- Accessible color contrast.
- Consistent spacing and typography.
- Clear status indicators.
- Professional charts and tables.
- Light and dark themes.

Avoid excessive gradients, decorative animations and generic AI landing-page designs.

### Main navigation

- Overview.
- Products.
- Market Entry.
- Regulatory Research.
- Compliance Assessments.
- Documents.
- Label Review.
- Regulatory Monitoring.
- Reports.
- Team.
- Settings.

### Dashboard

Display:

- Active products.
- Target markets.
- Ongoing assessments.
- Missing documents.
- Regulatory alerts.
- Recently updated regulations.
- Compliance task progress.
- Recent activity.

Do not display fake live metrics or fabricated regulatory statistics.

### Main user workflow

A user should be able to:

1. Create a company workspace.
2. Add a product.
3. Select a destination market.
4. Provide product details.
5. Upload available documents.
6. Run a regulatory assessment.
7. Review cited requirements.
8. Identify missing evidence.
9. Assign tasks to team members.
10. Generate a report.
11. Subscribe to regulatory monitoring.

## 12. ADMINISTRATION

Create a secure internal administration system.

Admin capabilities:

- Organization management.
- User management.
- Subscription management.
- Regulatory source management.
- Connector health.
- Data synchronization monitoring.
- Regulatory record review.
- Source verification.
- AI provider configuration.
- Usage monitoring.
- Audit log review.
- Error monitoring.
- Background job management.

Implement a separate administrative permission model.

Require stronger authentication for privileged access.

All changes to regulatory knowledge must be auditable.

## 13. BILLING AND COMMERCIAL MODEL

Build billing as a modular service.

Potential plans:

- Free Trial.
- Starter.
- Professional.
- Business.
- Enterprise.

Possible usage dimensions:

- Number of products.
- Number of target markets.
- Document processing volume.
- Regulatory monitoring subscriptions.
- Team seats.
- Report generation.
- Advanced integrations.

Do not hardcode payment-provider assumptions.

Build a payment abstraction layer and select a provider based on business registration, geographic availability and supported currencies.

Use verified webhook signatures and idempotency.

Never store raw card numbers or CVV values.

Keep billing independent from regulatory analysis.

## 14. OBSERVABILITY AND RELIABILITY

Implement:

- Structured logs.
- Error tracking.
- Metrics.
- Health checks.
- Distributed tracing where useful.
- Background job monitoring.
- Database monitoring.
- Source connector monitoring.
- AI provider monitoring.

Reliability requirements:

- Retry policies.
- Exponential backoff.
- Idempotent jobs.
- Dead-letter handling.
- Graceful degradation.
- Timeouts.
- Circuit breakers.
- Backup and recovery strategy.

A failed external source must not silently produce a successful-looking compliance result.

## 15. TESTING STRATEGY

Implement:

### Unit tests

- Regulatory applicability.
- Classification logic.
- Document extraction.
- Permission checks.
- Source parsing.
- Evidence validation.

### Integration tests

- Database.
- Authentication.
- API.
- Storage.
- Background jobs.
- Regulatory connectors.
- AI providers.

### Security tests

- Tenant isolation.
- Broken access control.
- IDOR.
- SQL injection.
- XSS.
- CSRF.
- File upload attacks.
- Prompt injection.
- Secret leakage.
- Privilege escalation.

### End-to-end tests

Test the complete user workflow.

### Regulatory accuracy tests

Build a curated test dataset with manually verified official sources.

Measure:

- Citation correctness.
- Requirement extraction accuracy.
- Applicability precision.
- Missing requirement rate.
- False positive rate.
- False negative rate.
- Source freshness.

Do not use an LLM's own confidence score as proof of regulatory correctness.

## 16. DEVELOPMENT PHASES

### PHASE 0 — Discovery and Architecture

Inspect the existing repository before changing anything.

Identify:

- Existing framework.
- Existing files.
- Existing code.
- Existing database.
- Dependencies.
- Deployment configuration.
- Existing security weaknesses.

Create or update all architecture and product documentation.

Produce:

- PRD.
- Technical architecture.
- Database ERD.
- API design.
- Security threat model.
- Regulatory source strategy.
- MVP scope.
- Implementation roadmap.

Do not delete working code.

Do not silently replace existing infrastructure.

At the end of Phase 0, present findings, architecture decisions, risks and implementation plan.

STOP and request approval before making major architectural changes.

### PHASE 1 — Secure Foundation

Build:

- Monorepo.
- Authentication.
- Organizations.
- RBAC.
- Tenant isolation.
- Database migrations.
- Secure file storage.
- Basic audit logs.
- CI checks.

### PHASE 2 — Product and Market Workflows

Build:

- Product profiles.
- Countries and jurisdictions.
- Market entry projects.
- Product classification assistance.
- Regulatory source registry.

### PHASE 3 — Regulatory Knowledge Engine

Build:

- Source connectors.
- Regulation records.
- Versioning.
- Retrieval.
- Evidence tracking.
- Citation validation.

Start with a small number of verified official sources and markets.

### PHASE 4 — Document Intelligence

Build:

- File uploads.
- OCR.
- Document extraction.
- Structured validation.
- Compliance gap analysis.

### PHASE 5 — Market Entry Assessments

Build:

- Requirement mapping.
- Applicability analysis.
- Assessment workflow.
- Human review.
- Compliance reports.

### PHASE 6 — Regulatory Monitoring

Build:

- Source synchronization.
- Change detection.
- Version comparison.
- Impact assessment.
- Alerts.

### PHASE 7 — Commercial Platform

Build:

- Pricing plans.
- Usage limits.
- Billing integration.
- Subscription lifecycle.
- Enterprise features.

### PHASE 8 — Production Hardening

Complete:

- Security audit.
- Performance testing.
- Backup and restore testing.
- Accessibility.
- Documentation.
- Monitoring.
- Deployment.
- Incident response procedures.

## 17. MVP ACCEPTANCE CRITERIA

The first production-oriented MVP is not complete until:

1. A company can register securely.
2. Users can create an organization and product.
3. Users can select a supported target market.
4. The platform retrieves actual verified regulatory records from supported official sources.
5. Every regulatory finding has a traceable source.
6. The platform distinguishes active, proposed and repealed regulations.
7. Users can upload documents securely.
8. The platform can identify missing document information.
9. Compliance findings show their evidence and uncertainty.
10. Users can generate versioned reports.
11. Organization data is isolated.
12. Sensitive actions are audited.
13. Tests cover critical workflows and security boundaries.
14. The application does not invent legal requirements.
15. Unsupported countries and product categories are clearly identified.

## 18. IMPORTANT ENGINEERING RULES

- Do not fake data integrations.
- Do not invent regulatory records.
- Do not use mock data in production.
- Do not expose secrets.
- Do not bypass authorization.
- Do not trust client-side validation.
- Do not automatically certify products.
- Do not claim universal country coverage.
- Do not generate unsupported legal conclusions.
- Do not use scraped secondary websites as authoritative legal sources.
- Do not silently ignore failed regulatory synchronization.
- Do not build unnecessary features before the core workflow works.

Use mock data only in clearly labeled development and testing environments.

## 19. FINAL PRODUCT QUALITY

The final product should feel like a serious international enterprise software company built it.

Prioritize:

- Correctness.
- Trust.
- Security.
- Regulatory evidence.
- Excellent UX.
- Maintainability.
- Scalability.
- Clear documentation.
- Reliable integrations.

Every major feature must have documentation and tests.

Make architecture decisions explicitly and explain trade-offs.

When a requirement is ambiguous, document the ambiguity instead of making an unsafe assumption.

## 20. YOUR FIRST TASK

Start with Phase 0 only.

Inspect the existing project.

Create the product requirements, architecture, database design, threat model, regulatory data strategy and phased implementation roadmap.

Do not start building the entire application blindly.

Do not delete or overwrite existing working files.

At the end, provide:

1. Repository assessment.
2. Proposed architecture.
3. Technology decisions.
4. Database ERD.
5. Security assessment.
6. Regulatory source integration plan.
7. MVP scope.
8. Development milestones.
9. Risks and unresolved questions.

Then stop and wait for my approval before proceeding to Phase 1.

Build ReguLens as a serious, evidence-based international regulatory intelligence platform — not an AI chatbot pretending to know every country's laws.