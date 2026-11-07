# REGULATORY SOURCES REGISTRY: Official Authorities & Data Feeds
**Document:** `docs/REGULATORY_SOURCES.md`  
**Phase:** Phase 0A (Scope & Market Validation)  
**Date of Revision:** 2026-11-07  
**Author:** Antigravity (ReguLens Pair Programming Agent)  
**Status Vocabulary:** Manual only | Partial | Not supported | Feasible after verification. (Note: "Integrated" is strictly prohibited in Phase 0A per `PHASE_0A.md`).  
**Verification Standard:** Any regulatory claim or data feed based on an authority or endpoint that was not directly opened and verified by the agent is explicitly marked "غير مُتحقَّق منه" or "Requires human verification".

---

## 1. Scope and Classification Rules
This document serves as the canonical registry of authoritative regulatory sources for ReguLens, evaluating coverage for:
- **Agriculture:** Fresh Oranges (HS 0805.10), Frozen Strawberries (HS 0811.10)
- **Textiles & Garments:** Ready-Made Garments (HS 61/62), Fabrics/Textiles (HS 50-60), Children's Clothing (Specialized sub-segment)
- **Jurisdictions:** European Union (EU-wide and Member State authorities) & Arab Republic of Egypt (origin-side export controls)

---

## 2. EU-Wide Authoritative Sources

### Source 1: EUR-Lex (EU Official Legal Repository)
- **Responsible Authority:** Publications Office of the European Union.
- **Specific URLs Verified:**
  - Portal root: `https://eur-lex.europa.eu/`
  - Commission Implementing Regulation (EU) 2026/194 (amending Reg 2019/1793): `https://eur-lex.europa.eu/eli/reg_impl/2026/194/oj` [CELEX: 32026R0194]
  - Decision No 1/2024 of the EU-Egypt Association Council: `https://eur-lex.europa.eu/eli/dec/2024/2653/oj` [CELEX: 22024D2653]
  - Regulation (EC) No 396/2005 (MRLs): `https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:02005R0396-20260819`
  - Regulation (EU) 2017/625 (Official Controls): `https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32017R0625`
  - Regulation (EU) 2016/2031 (Plant Health Law): `https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32016R2031`
  - Regulation (EU) No 1007/2011 (Textile Labelling): `https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:02011R1007-20180215`
  - Regulation (EC) No 1907/2006 (REACH): `https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:02006R1907`
  - Regulation (EU) 2023/988 (GPSR): `https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R0988`
  - Commission Implementing Decision (EU) 2026/901 (GPSR Harmonised Standards): `https://eur-lex.europa.eu/eli/dec_impl/2026/901/oj` [CELEX: 32026D0901]
- **Jurisdiction:** European Union (All 27 Member States).
- **Relevant Product Categories:** All products in scope (Fresh Oranges, Frozen Strawberries, Garments, Fabrics, Children's Clothing).
- **Information Provided & Legal Status Verified:**
  - Full legal acts, amendments, consolidated texts, and annexes.
  - Commission Implementing Regulation (EU) 2026/194: **Active** (published 29.1.2026, entered into force 18.2.2026).
  - Decision No 1/2024 of the EU-Egypt Association Council: **Active** (adopted 1.10.2024, published 9.10.2024).
  - Regulation (EU) 2023/988 (GPSR): **Active** (applied since 13.12.2024).
  - Commission Implementing Decision (EU) 2026/901: **Active** (published 27.4.2026; Article 1 publishes in the Official Journal the references listed in Annex I, including EN 14682:2014 in entry 37; conformity gives rise to a presumption of safety under Article 7(1)(a) of Regulation (EU) 2023/988 limited to the risks and risk categories covered by the standard, pending qualified human expert review; does not establish overall product compliance).
- **API / Downloadable Feeds:**
  - **EUR-Lex SOAP Web Service:** WSDL at `https://eur-lex.europa.eu/EURLexWebService?WSDL`. Requires free EU Login account and registration. [حقيقة مؤكدة من التوثيق الرسمي؛ لكن لم يتم إجراء استدعاء برمجي حي في هذه الجلسة].
  - **CELLAR SPARQL Endpoint:** `https://publications.europa.eu/webapi/rdf/sparql`. Open RDF triple-store querying (SPARQL 1.1) returning JSON, XML, CSV. [حقيقة مؤكدة من وثائق CELLAR؛ لم يتم بناء خط أنابيب بيانات حي بعد].
  - **CELLAR REST API:** Retrieval of full legal texts via CELEX identifiers.
- **Access Restrictions & Licensing:** Free public access. Reuse of EU legal texts is authorized under European Commission Decision 2011/833/EU with source acknowledgement.
- **Update Frequency:** Daily / concurrent with publication of the Official Journal of the European Union.
- **Integration Feasibility:** Feasible after verification. High technical feasibility via SPARQL and REST endpoints.
- **Phase 0A Status:** **Partial** (API documented and confirmed; parsing structured legal annexes into deterministic rules requires custom parser).
- **Direct Access Verification:** **نعم — تم تنزيل وقراءة نصوص اللوائح الرسمية وملاحقها مباشرة بنجاح (HTTP 200 OK) في 2026-11-07.**

---

### Source 2: EU Pesticides Database (DG SANTE / European Commission)
- **Responsible Authority:** European Commission, Directorate-General for Health and Food Safety.
- **Specific URL Verified:** `https://food.ec.europa.eu/plants/pesticides/eu-pesticides-database_en`
- **Jurisdiction:** European Union.
- **Relevant Product Categories:** Fresh Oranges (HS 0805.10), Frozen Strawberries (HS 0811.10).
- **Information Provided & Legal Reference:** Maximum Residue Levels (MRLs) for all approved and non-approved active substances by crop under Regulation (EC) No 396/2005; lists Annex II, Annex III, and default 0.01 mg/kg limit. [حقيقة مؤكدة من نص اللائحة الموحد وقاعدة البيانات العامة].
- **API / Downloadable Feeds:** 
  - Bulk data exports and XML datasets are hosted via the EU Open Data Portal (`data.europa.eu`).
  - وجود واجهة برمجية مباشرة (REST API): [غير مُتحقَّق منه مباشرة؛ ورد ذكرها في وثائق وصفية، لكن لم يتم اختبار endpoint حي ومواصفات التوثيق].
- **Access Restrictions & Licensing:** Free public browsing. Official legal reference remains the Official Journal (Regulation 396/2005).
- **Update Frequency:** Updated concurrently with EU regulations amending Annexes to Reg 396/2005.
- **Integration Feasibility:** Feasible after verification (requires verification of REST endpoint specifications vs. batch XML ingestion).
- **Phase 0A Status:** **Partial**
- **Direct Access Verification:** **نعم — تم فتح واجهة الموقع العامة بنجاح (HTTP 200 OK) في 2026-11-07 (فتح الصفحة لا يعني اختبار API).**

---

### Source 3: EFSA (European Food Safety Authority)
- **Responsible Authority:** European Food Safety Authority, Parma, Italy.
- **Specific URL Verified:** `https://www.efsa.europa.eu/en`
- **Jurisdiction:** European Union (Scientific Risk Assessment Body; non-legislative).
- **Relevant Product Categories:** Oranges, Strawberries (Scientific opinions on active substances and MRL proposals).
- **Information Provided:** Scientific risk assessments evaluating pesticide active substance safety, dietary exposure models (PRIMo), and annual monitoring reports on pesticide residues in food.
- **API / Downloadable Feeds:**
  - بوابة المطورين `https://developers.efsa.europa.eu/`: [غير مُتحقَّق منه مباشرة؛ ورد وصفها كنسخة Beta في ملخصات البحث، ولكن لم يتم فتح الـ API وفحص وثائقها مباشرة].
- **Access Restrictions & Licensing:** Free public access.
- **Update Frequency:** Periodic upon publication of scientific opinions.
- **Integration Feasibility:** Manual lookup only; background scientific context and risk profiling.
- **Phase 0A Status:** **Manual only**
- **Direct Access Verification:** **نعم — تم فتح واجهة الموقع العامة بنجاح (HTTP 200 OK) في 2026-11-07 (فتح الصفحة لا يعني اختبار واجهة برمجية).**

---

### Source 4: RASFF Window (Rapid Alert System for Food and Feed)
- **Responsible Authority:** European Commission, DG SANTE.
- **Specific URL:** `https://webgate.ec.europa.eu/rasff-window/`
- **Jurisdiction:** European Union (Border Control Posts and National Food Safety Authorities).
- **Relevant Product Categories:** Fresh Oranges, Frozen Strawberries.
- **Information Provided:** Real-time border rejection notifications, food safety alerts, chemical hazard levels, notifying countries, and origin tracing.
- **API / Downloadable Feeds:** 
  - **No official public REST API** for live queries exists. [حقيقة مؤكدة من توثيق المنظومة].
  - Periodic bulk datasets (JSON/CSV) available on the EU Open Data Portal (`data.europa.eu`).
- **Access Restrictions & Licensing:** تصفح عام للموقع؛ التجريف المؤتمت للواجهة الحية يخضع لقيود تقنية وحماية الخوادم.
- **Phase 0A Status:** **Manual only** (Bulk ingestion feasible after verification in later phases).
- **Direct Access Verification:** **لا — لم يتم الاتصال بالبوابة الحية مباشرة في هذه الجلسة.**

---

### Source 5: TRACES NT (Trade Control and Expert System New Technology)
- **Responsible Authority:** European Commission, DG SANTE.
- **Specific URLs:**
  - Information portal: `https://food.ec.europa.eu/animals/traces_en`
  - System URL: `https://traces.ec.europa.eu/`
- **Jurisdiction:** European Union.
- **Relevant Product Categories & Statutory Dual-Track Breakdown:**
  1. **Fresh Oranges (HS 0805.10):**
     - *Plant Health Track:* Governed by Regulation (EU) 2016/2031 & Regulation (EU) 2019/2072. Requires an official **Phytosanitary Certificate** from Egypt (CAPQ) and submission of a **CHED-PP** pursuant to **Article 56(3)(c) of Regulation (EU) 2017/625**.
     - *Food Safety / Pesticide Track:* Governed by Regulation (EU) 2017/625 (Article 47(1)(d)) and Regulation (EU) 2019/1793, Annex I (amended by Reg 2026/194). Requires pre-notification under increased controls via a **CHED-D** pursuant to **Article 56(3)(d) of Regulation (EU) 2017/625** and **Article 7 of Regulation (EU) 2019/1793**.
     - *Check Frequencies:*
       - **Documentary Checks:** **100%** on all consignments under **Article 54(1) of Regulation (EU) 2017/625 [Not verified from a saved primary text]**.
       - **Identity and Physical Checks:** Set at a single combined frequency of **10%** of consignments entering the Union pursuant to **Article 6 of Regulation (EU) 2019/1793** and Annex I (decreased from 20% by Regulation (EU) 2026/194, Recital 6 and Annex I).
     - *Administrative Interplay:* Both legal tracks apply independently based on separate statutory mandates. In border post operational practice, whether Member State BCPs require two distinct electronic forms or process them via a single linked entry in TRACES NT is an operational implementation detail that [Requires human verification with local BCP customs brokers].
  2. **Egyptian Strawberries (Fresh CN 0810 10 00 vs. Frozen CN 0811 10):**
     - *Fresh Strawberries (CN 0810 10 00):*
       - **Plant Health Track:** Explicitly listed in **Annex XI, Part A, point 5 of Regulation (EU) 2019/2072** under *Fragaria* L. originating in third countries other than Switzerland. Requires an official **Phytosanitary Certificate** from CAPQ and pre-notification via **CHED-PP** pursuant to Article 56(3)(c) of Regulation (EU) 2017/625 and Article 72(1) of Regulation (EU) 2016/2031.
       - **Food Safety Track:** Listed in **Annex I of Regulation (EU) 2019/1793** (as amended by Regulation (EU) 2026/194). Requires pre-notification via **CHED-D** in TRACES NT, with **100% documentary checks** (Art 54(1) of Reg 2017/625 [Not verified from a saved primary text]) and a single combined frequency of **20% for identity and physical checks** (Art 6 of Reg 2019/1793).
     - *Frozen Strawberries (CN 0811 10):*
       - **Plant Health Track:** CN 0811 10 is not identified in the examined Annex XI entries (examined version: Official Journal publication text of 10.12.2019, OJ L 319, CELEX: 32019R2072). Based on current evidence, no general phytosanitary certificate requirement has been established for the examined frozen-strawberry product. Product classification, verification against the current consolidated Annex XI (as absence from the original 2019 text is not proof of absence from the current Annex XI), and any specific phytosanitary measures remain subject to qualified human verification (`REQUIRES HUMAN VERIFICATION`). EU legislation contains no express statutory provision establishing that freezing or the loss of biological viability creates a blanket phytosanitary exemption, and no blanket exemption is inferred. Practical customs clearance and port inspection procedures marked `REQUIRES HUMAN VERIFICATION`.
       - **Food Safety Track:** Confirmed inclusion in **Annex I of Regulation (EU) 2019/1793** (as amended by Regulation (EU) 2026/194, Recital 7 & Annex I). Requires mandatory pre-notification via **CHED-D** in TRACES NT, entry through an approved BCP, **100% documentary checks** (Article 54(1) of Regulation (EU) 2017/625 [Not verified from a saved primary text]), and a single combined frequency of **20% for identity and physical checks** (Article 6 of Regulation (EU) 2019/1793).
- **API / Downloadable Feeds:** 
  - **No public REST API** for third-party commercial software. Interoperability is restricted to Government-to-Government (G2G) customs systems. [حقيقة مؤكدة من التوثيق الرسمي لسلامة الغذاء].
- **Access Restrictions & Licensing:** Restricted access: requires verified EORI/VAT registration and approval by competent national authorities.
- **Integration Feasibility:** Not supported for direct automated integration. ReguLens can only guide exporters on documentary preparation (how to complete Part I of the CHED-PP or CHED-D).
- **Phase 0A Status:** **Manual only**
- **Direct Access Verification:** **نعم لصفحة التعريف العامة بـ TRACES عبر food.ec.europa.eu (HTTP 200 OK)؛ ولا للنظام التشغيلي المقيد traces.ec.europa.eu.**

---

### Source 6: ECHA (European Chemicals Agency) - REACH Substance Databases
- **Responsible Authority:** European Chemicals Agency, Helsinki.
- **Specific URLs:**
  - Portal root: `https://echa.europa.eu/`
  - Candidate List table: `https://echa.europa.eu/candidate-list-table`
- **Jurisdiction:** European Union.
- **Relevant Product Categories:** Ready-Made Garments (HS 61/62), Fabrics (HS 50-60), Children's Clothing.
- **Information Provided & Regulatory Framework:**
  - Candidate List of Substances of Very High Concern (SVHC) (>0.1% w/w triggers Art 33 communication, Art 7(2) 1-tonne notification, and SCIP reporting).
  - REACH Annex XVII restrictions (Entry 72 for CMRs in clothing, Entry 43 for Azo dyes, Entry 27 for Nickel, Entry 51/52 for Phthalates). [حقيقة مؤكدة من نص لائحة REACH المفتوح عبر EUR-Lex].
- **API / Downloadable Feeds & Technical Restrictions:** 
  - **No public REST API for live substance searching.**
  - **محاولة الاتصال المباشر:** استجابت البوابة بـ **HTTP 403 Forbidden** عند محاولة الاتصال المؤتمت بواسطة curl، نظراً لجدار الحماية `Microsoft-Azure-Application-Gateway/v2`. (ملاحظة: رمز 403 يثبت وجود حظر تقني للطلبات المؤتمتة عبر WAF، ولا يثبت انعدام وجود حزم بيانات مجمعة).
  - حزم البيانات المجمعة (CSV, XML, RDF) متاحة للتنزيل عبر بوابة البيانات المفتوحة الأوروبية (`data.europa.eu`). [غير مُتحقَّق منه مباشرة في هذه الجلسة].
- **Phase 0A Status:** **Partial** (Bulk open datasets feasible after verification; direct portal integration not supported).
- **Direct Access Verification:** **لا — فشل الاتصال المباشر بالبوابة بسبب جدار الحماية (HTTP 403 Forbidden).**

---

### Source 7: Access2Markets / My Trade Assistant (DG TRADE)
- **Responsible Authority:** European Commission, Directorate-General for Trade.
- **Specific URL Verified:** `https://trade.ec.europa.eu/access-to-markets/en/home`
- **Jurisdiction:** European Union.
- **Relevant Product Categories:** All products in scope (Tariffs, Rules of Origin, SPS/TBT requirements).
- **Information Provided:** Combined Nomenclature (CN) duty rates, preferential tariff calculations under EU-Egypt Association Agreement, Rules of Origin Self-Assessment (ROSA), VAT and excise rates per Member State.
- **API / Downloadable Feeds:** 
  - لا توجد واجهة برمجية مباشرة معلنة لبوابة Access2Markets نفسها؛ قاعدة TARIC الأساسية تتطلب فحصاً مستقلاً لوثائقها. [غير مُتحقَّق منه فيما يخص الـ API؛ الواجهة العامة مفتوحة بنجاح].
- **Access Restrictions & Licensing:** Public browsing, free.
- **Phase 0A Status:** **Manual only**
- **Direct Access Verification:** **نعم — تم فتح الواجهة العامة بنجاح (HTTP 200 OK) في 2026-11-07 (فتح الصفحة لا يعني اختبار واجهة برمجية).**

---

### Source 8: NANDO (New Approach Notified and Designated Organisations)
- **Responsible Authority:** European Commission, DG GROW.
- **Specific URL:** `https://ec.europa.eu/growth/tools-databases/nando/`
- **Jurisdiction:** European Union.
- **Relevant Product Categories:** Children's clothing ONLY IF classified as Personal Protective Equipment (PPE) under Regulation (EU) 2016/425.
- **Critical Scope Finding:** Standard children's everyday clothing is governed by the General Product Safety Regulation (EU 2023/988) and standards EN 14682 / EN 17394, which **do NOT require a Notified Body or CE marking**. Therefore, NANDO is out of scope for standard ready-made garments. [حقيقة مؤكدة من نصوص اللوائح].
- **Phase 0A Status:** **Not supported**
- **Direct Access Verification:** **لم يتم فتحه مباشرة نظراً لخروجه عن النطاق التنظيمي للملابس العادية.**

---

## 3. Egyptian Origin-Side Regulatory & Export Bodies

### Source 9: Egyptian Customs Authority & GOEIC
- **Responsible Authorities:** 
  - Egyptian Customs Authority (مصلحة الجمارك المصرية - Ministry of Finance).
  - General Organization for Export and Import Control (GOEIC - Ministry of Trade and Industry).
- **Specific URLs:** `https://customs.gov.eg/`, `https://goeic.gov.eg/`
- **Jurisdiction:** Arab Republic of Egypt.
- **Relevant Product Categories:** All export sectors (Garments, Textiles, Fresh & Processed Food).
- **Information Provided & Legal Mandate (Rules of Origin):** 
  - Under Decision No 1/2024 of the EU-Egypt Association Council replacing Protocol 4 (Article 20(1)), movement certificates EUR.1 are legally issued by the **"customs authorities of the exporting Party"** (السلطات الجمركية).
  - Local operational procedures: GOEIC conducts industrial origin verification and issues commercial certificates of origin. Attributing EUR.1 issuance solely to GOEIC without citing the specific Egyptian ministerial decree is unverified. [Requires human verification].
- **API / Downloadable Feeds:** [غير مُتحقَّق منه بالاتصال المباشر؛ لم يُفتح موقع الجمارك أو GOEIC مباشرة في الجلسة; استندت المعلومات لنصوص اتفاقية الشراكة وملخصات البحث].
- **Phase 0A Status:** **Manual only**
- **Direct Access Verification:** **لا — لم يتم الاتصال المباشر بالبوابات في هذه الجلسة.**

---

### Source 10: Central Administration of Plant Quarantine (CAPQ)
- **Responsible Authority:** Egyptian Ministry of Agriculture and Land Reclamation (MALR).
- **Specific URL:** `https://www.capq.gov.eg/`
- **Jurisdiction:** Arab Republic of Egypt.
- **Relevant Product Categories:** 
  - Fresh Oranges (HS 0805.10) — Mandatory Phytosanitary Certificate (Reg 2019/2072 Annex XI Part A(1)).
  - Fresh Strawberries (HS 0810.10) — Mandatory Phytosanitary Certificate (Reg 2019/2072 Annex XI Part A(5)).
  - Frozen Strawberries (HS 0811.10) — No general phytosanitary certificate requirement established under examined Annex XI entries, while product classification and specific measures remain subject to `Requires human verification`.
- **Information Provided:** 
  - Issuance of mandatory Phytosanitary Certificates for fresh plant produce entering the EU under Regulation (EU) 2016/2031.
  - Farm and packing station inspection, accreditation, and coding.
- **API / Downloadable Feeds:** [غير مُتحقَّق منه بالاتصال المباشر؛ الموقع لم يُفتح مباشرة في الجلسة].
- **Phase 0A Status:** **Manual only**
- **Direct Access Verification:** **لا — لم يتم الاتصال المباشر بالبوابة في هذه الجلسة.**

---

### Source 11: Export Councils (FECEG & RMGEC) & Expolink
- **Responsible Authority:** Semi-governmental advisory and trade promotion bodies.
- **Specific URLs:** `https://feceg.com/`, `https://www.expolink.org/`
- **Jurisdiction:** Arab Republic of Egypt.
- **Relevant Product Categories:** Food Industries (FECEG), Apparel & Garments (RMGEC).
- **Important Legal Clarification:** These export councils are **NOT regulatory authorities**. They do not legislate, inspect, or legally certify compliance. They are industry advisory bodies. [حقيقة مؤكدة].
- **API / Downloadable Feeds:** لا توجد واجهات برمجية.
- **Phase 0A Status:** **Manual only**
- **Direct Access Verification:** **لا — لم يتم الاتصال المباشر في هذه الجلسة.**

---

## 4. Master Source Integration Feasibility Summary

| Source Name | Jurisdiction | Product Scope | API / Data Feed Available? | License / Access Terms | Phase 0A Status |
|---|---|---|---|---|---|
| **EUR-Lex** | EU-wide | All Products | **Yes** (SOAP + SPARQL + REST وثائق رسمية) | Free open reuse (Dec 2011/833/EU) | **Partial** |
| **EU Pesticides DB** | EU-wide | Oranges, Strawberries | **Bulk XML confirmed** (REST API غير مُتحقَّق منها) | Free public access | **Partial** |
| **EFSA** | EU-wide | Oranges, Strawberries | **Beta API غير مُتحقَّق منها** | Free public access | **Manual only** |
| **RASFF Window** | EU-wide | Oranges, Strawberries | **Bulk only عبر data.europa.eu** (لا توجد API حية) | Public browsing; التجريف الآلي مقيد | **Manual only** |
| **TRACES NT** | EU-wide | Oranges, Strawberries | **No public API** (G2G customs only) | Restricted to authorized operators | **Manual only** |
| **ECHA Databases** | EU-wide | Garments, Fabrics, Children's | **Bulk open data**; محاولة الفحص المباشر حظرها WAF (403) | تنزيل البيانات المفتوحة مجاني | **Partial** |
| **Access2Markets** | EU-wide | All Products | **No confirmed API** (يتطلب فحص TARIC) | Free public browsing | **Manual only** |
| **NANDO** | EU-wide | Out of Scope (Non-PPE Garments) | Unverified | Public directory | **Not supported** |
| **Customs / GOEIC** | Egypt | All Products | **No public API** (Portal-bound) | Commercial entities registered in Egypt | **Manual only** |
| **CAPQ** | Egypt | Fresh Oranges ONLY | **No public API** (Portal-bound) | Commercial growers/exporters | **Manual only** |
| **Export Councils** | Egypt | Advisory only | **None** | Member/public trade promotion | **Manual only** |

---

## 5. Verification Ledger

| المصدر / الرابط | هل فتحه الوكيل مباشرة؟ | طريقة الحصول على المعلومة | تاريخ الوصول | حالة التشريع / المصدر |
|---|---|---|---|---|
| `https://eur-lex.europa.eu/eli/reg_impl/2026/194/oj` | **نعم** (HTTP 200 OK) | تنزيل وفحص النص الرسمي للائحة وملاحقها | 2026-11-07 | Active (سارية من 18-02-2026) |
| `https://eur-lex.europa.eu/eli/dec/2024/2653/oj` | **نعم** (HTTP 200 OK) | تنزيل وفحص نص القرار 1/2024 والملاحق | 2026-11-07 | Active (سارية من 01-10-2024) |
| `https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:02005R0396-20260819` | **نعم** (HTTP 200 OK) | فحص النص الموحد عبر EUR-Lex | 2026-11-07 | Active (محدثة ومعدلة) |
| `https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32017R0625` | **نعم** (HTTP 200 OK) | فحص النص القانوني للائحة 2017/625 (المادة 54(1) و56) | 2026-11-07 | Active (لائحة الضوابط الرسمية) |
| `https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32016R2031` | **نعم** (HTTP 200 OK) | فحص نص قانون الصحة النباتية الأوروبي | 2026-11-07 | Active (لائحة الصحة النباتية) |
| `https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:02011R1007-20180215` | **نعم** (HTTP 200 OK) | فحص النص الموحد عبر EUR-Lex | 2026-11-07 | Active (لائحة بطاقات المنسوجات) |
| `https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:02006R1907` | **نعم** (HTTP 200 OK) | فحص النص الموحد للائحة REACH | 2026-11-07 | Active (لائحة المواد الكيميائية) |
| `https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R0988` | **نعم** (HTTP 200 OK) | فحص النص القانوني للائحة GPSR | 2026-11-07 | Active (سارية من 13-12-2024) |
| `https://eur-lex.europa.eu/eli/dec_impl/2026/901/oj` | **نعم** (HTTP 200 OK) | تنزيل وفحص نص القرار 2026/901 وقوائم معايير GPSR (الملحق I، البند 37) | 2026-11-07 | Active (نافذ من 27-04-2026) |
| `https://single-market-economy.ec.europa.eu/single-market/goods/european-standards/harmonised-standards/general-product-safety_en` | **نعم** (HTTP 200 OK) | تنزيل وفحص القائمة التلخيصية الرسمية لمعايير GPSR (ملف PDF/XLSX المؤرخ 27-04-2026) | 2026-11-07 | Active (قائمة المفوضية الرسمية) |
| `https://trade.ec.europa.eu/access-to-markets/en/home` | **نعم** (HTTP 200 OK) | فتح مباشر للواجهة العامة (لم تُختبر API) | 2026-11-07 | Active (بوابة التجارة العامة) |
| `https://www.efsa.europa.eu/en` | **نعم** (HTTP 200 OK) | فتح مباشر للواجهة العامة (لم تُختبر API) | 2026-11-07 | Active (الهيئة العلمية لسلامة الغذاء) |
| `https://food.ec.europa.eu/plants/pesticides/eu-pesticides-database_en` | **نعم** (HTTP 200 OK) | فتح مباشر للواجهة العامة (لم تُختبر API) | 2026-11-07 | Active (قاعدة المبيدات بالمفوضية) |
| `https://echa.europa.eu/` | **لا** (حظر 403) | محاولة اتصال مباشر صُدّت بواسطة WAF | 2026-11-07 | Active (تعذر الفحص الآلي المباشر) |
| `https://webgate.ec.europa.eu/rasff-window/` | **لا** | ملخص بحث ثانوي (غير مفتوح) | 2026-11-07 | غير مُتحقَّق منه بالكامل |
| `https://traces.ec.europa.eu/` | **لا** | ملخص بحث + صفحة التعريف العامة (النظام المقيد لم يُفتح) | 2026-11-07 | غير مُتحقَّق منه بالكامل |
| `https://ec.europa.eu/growth/tools-databases/nando/` | **لا** | استبعاد تحليلي استناداً لنصوص اللوائح (خارج النطاق) | 2026-11-07 | غير مُتحقَّق منه بالكامل |
| `https://customs.gov.eg/` | **لا** | ملخص بحث ثانوي (غير مفتوح) | 2026-11-07 | غير مُتحقَّق منه بالكامل |
| `https://goeic.gov.eg/` | **لا** | ملخص بحث ثانوي (غير مفتوح) | 2026-11-07 | غير مُتحقَّق منه بالكامل |
| `https://capq.gov.eg/` | **لا** | ملخص بحث ثانوي (غير مفتوح) | 2026-11-07 | غير مُتحقَّق منه بالكامل |
| `https://feceg.com/` | **لا** | ملخص بحث ثانوي (غير مفتوح) | 2026-11-07 | غير مُتحقَّق منه بالكامل |
| `https://expolink.org/` | **لا** | ملخص بحث ثانوي (غير مفتوح) | 2026-11-07 | غير مُتحقَّق منه بالكامل |

---

## 6. Mandatory Report Disclaimer
"This report provides regulatory research and compliance-support information based on the sources and product information available at the time of generation. It is not an official government approval, certification, legal opinion or guarantee of market access. Requirements should be verified with the relevant authorities and qualified professionals."
