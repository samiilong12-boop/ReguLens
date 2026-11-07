# MARKET RESEARCH: Egyptian Agri-Food & Textile Exports to the EU
**Document:** `docs/MARKET_RESEARCH.md`  
**Phase:** Phase 0A (Scope & Market Validation)  
**Date of Revision:** 2026-11-07  
**Author:** Antigravity (ReguLens Pair Programming Agent)  
**Evidence Standard:** Strict classification per `AGENTS.md` and `.agents/rules/TEAM_WORKFLOW.md`. Every regulatory claim carries an official citation with URL, authority, legal act reference, and lifecycle state. Any claim not directly verified against official databases is marked "غير مُتحقَّق منه" or "Requires human verification".

---

## 1. Transparency on Access & Methodology
- **Project Constitution Loaded:** `AGENTS.md` (read directly via `read_file` on 2026-11-07; rules 1 to 15 strictly observed).
- **Process & Roadmap Rules Loaded:** `.agents/rules/TEAM_WORKFLOW.md`, `.agents/rules/QUALITY_GATES.md`, `phases/ROADMAP.md`, `phases/PHASE_0A.md`.
- **Direct Official Network Probes (by Main Agent):**
  - `https://eur-lex.europa.eu/` (HTTP 200 OK — Official Journal and consolidated legislation directly fetched and verified).
  - `https://trade.ec.europa.eu/access-to-markets/en/home` (HTTP 200 OK — Trade portal interface reachable; live API not tested).
  - `https://www.efsa.europa.eu/en` (HTTP 200 OK — Public interface reachable; developer API not tested).
  - `https://food.ec.europa.eu/plants/pesticides/eu-pesticides-database_en` (HTTP 200 OK — Database public interface reachable; API endpoint not tested).
  - `https://echa.europa.eu/` (HTTP 403 Forbidden — Automated HTTP request rejected by Microsoft Azure Application Gateway WAF; does not prove absence of bulk data, but direct web scraping is technically blocked).
- **Official Legislative Texts Downloaded & Saved in Workspace (Primary Evidence):**
  - **Commission Implementing Regulation (EU) 2026/194** of 28 January 2026 (amending Implementing Regulation (EU) 2019/1793). [CELEX: 32026R0194; OJ L, 2026/194, 29.1.2026; Saved file: `reg_2026_194.html`; In force].
  - **Decision No 1/2024 of the EU-Egypt Association Council** of 1 October 2024 (replacing Protocol 4 of the Euro-Mediterranean Agreement). [CELEX: 22024D2653; OJ L, 2024/2653, 9.10.2024; Saved file: `decision_1_2024.html`; In force].
  - **Regulation (EU) 2016/2031** (Plant Health Law). [CELEX: 32016R2031; OJ L 317/4, 23.11.2016; Saved file: `reg_2016_2031.html`; Original 2016 text].
  - **Commission Implementing Regulation (EU) 2019/2072** (Uniform conditions for plant health). [CELEX: 32019R2072; OJ L 319/1, 10.12.2019; Saved file: `reg_2019_2072.html`; Original 2019 text examined; Annex XI requires verification against current consolidated version].
  - **Regulation (EU) 2023/988** (General Product Safety Regulation - GPSR). [CELEX: 32023R0988; OJ L 135/1, 23.5.2023; Saved file: `reg_2023_988.html`; Original 2023 text].
  - **Commission Implementing Decision (EU) 2026/901** of 17 April 2026. [CELEX: 32026D0901; OJ L, 2026/901, 27.4.2026; Saved file: `scratch/decision_2026_901.html`; In force].
- **Legal Acts Referenced but Not Saved as Local Primary Texts (Marked: Not verified from a saved primary text):**
  - **Regulation (EU) 2017/625** (Official Controls Regulation). [CELEX: 32017R0625; Not verified from a saved primary text].
  - **Regulation (EC) No 396/2005** (Pesticide MRLs). [CELEX: 02005R0396; Not verified from a saved primary text].
  - **Regulation (EC) No 1907/2006** (REACH). [CELEX: 02006R1907; Not verified from a saved primary text].
  - **Regulation (EU) No 1007/2011** (Textile Fibre Labelling). [CELEX: 02011R1007; Not verified from a saved primary text].
  - **Regulation (EU) 2019/1793** (Base Regulation; base 2019 text not saved, amending provisions verified from saved `reg_2026_194.html`).
- **Unverified Databases / Portals (Not opened directly; data cited from secondary search summaries):**
  - UN Comtrade, ITC Trade Map, Eurostat Comext raw database, live RASFF Window portal, GOEIC, CAPQ, Egyptian Export Councils (FECEG, RMGEC, Expolink).

---

## 2. Sector A: Agriculture & Food (Separate Analysis: Fresh Oranges vs. Frozen Strawberries)

### 2.1 Fresh Egyptian Oranges (HS 0805.10)
- **Trade Overview & Destination Markets:**
  - Egypt is a leading global citrus exporter (~1.8–2 million tonnes worldwide annually). [SUPPORTED FINDING / ESTIMATE: Secondary industry reports; not verified against primary Eurostat Comext or UN Comtrade bulk datasets].
  - Top entry gateways in the EU: The Netherlands (Port of Rotterdam as consolidation hub) and Spain (notable import spike in 2023/2024 due to drought-induced Spanish production shortfall). [SUPPORTED FINDING / ESTIMATE: Secondary market reports; not verified against primary Eurostat Comext database].

- **Dual Regulatory Regimes at EU Borders (Plant Health & Food Safety):**
  Fresh Egyptian oranges (CN code `0805 10`) fall under two distinct EU statutory control frameworks with independent legal bases:

  1. **Plant Health Regime (Phytosanitary Controls):**
     - *Scope & Purpose:* Prevention of introduction and spread of plant pests into the Union territory.
     - *Legal Basis:* Regulation (EU) 2016/2031 (Articles 72 and 74) and Commission Implementing Regulation (EU) 2019/2072 (Annex XI, Part A, point 1).
     - *Origin Document:* Official **Phytosanitary Certificate** issued by Egypt's National Plant Protection Organization (Central Administration of Plant Quarantine - CAPQ).
     - *EU Entry Clearance Document:* **CHED-PP** (Common Health Entry Document for Plants and Plant Products) governed by Article 56(3)(c) of Regulation (EU) 2017/625.
     - *Pre-Notification & Border Post:* Pre-notification via **TRACES NT** prior to physical arrival at a Border Control Post (BCP) designated for plants.
     - *Checks:* Documentary checks on 100% of consignments under Article 54(1) of Regulation (EU) 2017/625; identity and physical plant health checks at statutory EU plant health frequencies.

  2. **Food Safety / Pesticide Residue Regime (Increased Official Controls):**
     - *Scope & Purpose:* Protection of consumer health against chemical risks from pesticide residues exceeding EU MRLs under Regulation (EC) No 396/2005.
     - *Legal Basis:* Regulation (EU) 2017/625 (Article 47(1)(d)) and Commission Implementing Regulation (EU) 2019/1793, Annex I (as amended by Commission Implementing Regulation (EU) 2026/194).
     - *Commodity & CN Code:* Oranges (Food - fresh or dried), CN code `0805 10`, Country of origin: Egypt (EG).
     - *Check Frequencies:*
       - **Documentary Checks:** Conducted on **100% of consignments** entering the Union under Article 54(1) of Regulation (EU) 2017/625 [Not verified from a saved primary text].
       - **Identity and Physical Checks:** Set at a single combined frequency of **10% of consignments** entering the Union pursuant to **Article 6 of Regulation (EU) 2019/1793** and Annex I (decreased from 20% by Regulation (EU) 2026/194, Recital 6 and Annex I, reflecting verified improvements in compliance).
     - *EU Entry Clearance Document:* Food of non-animal origin listed in Annex I to Regulation (EU) 2019/1793 is governed by **Article 7 of Regulation (EU) 2019/1793** and Article 56(3)(d) of Regulation (EU) 2017/625, requiring declaration via a **CHED-D** (Common Health Entry Document for Feed and Food of Non-Animal Origin) pre-notified in TRACES NT.
     - *Administrative Interplay between CHED-PP and CHED-D:* Both legal regimes are legally applicable. However, whether Member State BCPs require two separate administrative CHED forms to be lodged or process them via a single linked entry in TRACES NT depends on specific BCP electronic interfaces (e.g. Rotterdam vs. Valencia vs. Hamburg) and [Requires human verification with BCP customs brokers].
     - *Origin Health Certificate Status:* Under Annex I of Regulation (EU) 2019/1793, consignments do NOT require an official model health certificate issued by Egyptian authorities under Article 11 (which applies strictly to Annex II commodities).

### 2.2 Egyptian Strawberries (Detailed Distinction: Fresh CN 0810 10 00 vs. Frozen CN 0811 10)

- **Trade Overview & Destination Markets:**
  - Egypt is a primary global supplier of Individual Quick Frozen (IQF) strawberries, with total worldwide exports estimated at over 350,000 tonnes. [SUPPORTED FINDING / ESTIMATE: Secondary industry publications; not verified against primary Eurostat Comext or UN Comtrade bulk datasets].
  - Primary EU markets: Germany (top industrial buyer for fruit processing/dairy), followed by Poland and the Netherlands. [SUPPORTED FINDING / ESTIMATE: Secondary trade reports; not verified against primary Eurostat Comext database].

- **Plant Health Regime (Phytosanitary Controls — Critical Legal Distinction):**
  1. **Fresh Strawberries (CN code `0810 10 00`):**
     - *Statutory Listing:* Explicitly listed in **Annex XI, Part A, point 5** of Commission Implementing Regulation (EU) 2019/2072 under the botanical genus *Fragaria* L. ("Strawberries, fresh or chilled: 0810 10 00").
     - *Legal Basis:* **Article 72(1) of Regulation (EU) 2016/2031**.
     - *Third-Country Origin:* Applies to all third countries other than Switzerland (including Egypt).
     - *Phytosanitary Requirement:* **MANDATORY Phytosanitary Certificate** issued by Egypt's National Plant Protection Organization (CAPQ).
     - *Border Clearance:* Mandatory pre-notification via **CHED-PP** (Common Health Entry Document for Plants and Plant Products) in TRACES NT under Article 56(3)(c) of Regulation (EU) 2017/625, entering via a designated plant Border Control Post (BCP).
  2. **Frozen Strawberries (CN code `0811 10`):**
     - *Examination of Annex XI of Commission Implementing Regulation (EU) 2019/2072:*
       - CN code `0811 10` ("Fruit and nuts, uncooked or cooked by steaming or boiling in water, frozen, whether or not containing added sugar or other sweetening matter: Strawberries") is not listed in **Annex XI, Part A** (plants, plant products and other objects for which a phytosanitary certificate is required under Article 72(1)) or **Annex XI, Part B** (plants for which a phytosanitary certificate is required under Article 73) of Regulation (EU) 2019/2072.
        - **Critical Version Caution:** The examined text of Regulation (EU) 2019/2072 was the original 2019 version (OJ L 319, 10.12.2019, CELEX: 32019R2072). Annex XI may have been amended since that version. Conclusions depending on the current Annex XI require verification against the applicable consolidated version (`REQUIRES HUMAN VERIFICATION`). The absence of CN 0811 10 from the original 2019 Annex XI cannot be presented as proof of its absence from the current Annex XI.
     - *No Blanket Exemption Inferred from Freezing:*
       - EU legislation contains no express statutory provision establishing that freezing or the loss of biological viability creates a blanket phytosanitary exemption. A blanket exemption cannot be inferred merely from freezing or loss of viability.
     - *Finding on Phytosanitary Certificate Requirement:*
       - CN 0811 10 is not identified in the examined Annex XI entries (examined version: Official Journal publication text of 10.12.2019, OJ L 319, CELEX: 32019R2072). Based on current evidence, no general phytosanitary certificate requirement has been established for the examined frozen-strawberry product. Product classification, verification against the current consolidated Annex XI, and any specific phytosanitary measures remain subject to qualified human verification (`REQUIRES HUMAN VERIFICATION`).
     - *Strict Distinction Between Four Legal Processes:*
       1. **Phytosanitary Certificate Requirement:** Plant health regime (Regulation (EU) 2016/2031 & Regulation (EU) 2019/2072); no general requirement established under examined original 2019 Annex XI entries; practical port clearance and customs classification marked `REQUIRES HUMAN VERIFICATION`.
       2. **CHED-D Pre-Notification:** Mandatorily required under food safety legislation (Regulation (EU) 2017/625 Art 47(1)(d) & Art 56(3)(d); Regulation (EU) 2019/1793 Art 7) in TRACES NT prior to arrival at a designated Border Control Post.
       3. **Documentary Checks:** Conducted on **100% of consignments** under Article 54(1) of Regulation (EU) 2017/625 [Not verified from a saved primary text]. This 100% documentary-check rate must not be confused with the identity and physical-check rate.
       4. **Identity and Physical Checks:** As supported by the exact quoted Egypt row from Annex I of Commission Implementing Regulation (EU) 2026/194, identity and physical checks are set at a single combined frequency of **20% of consignments** under Article 6 of Regulation (EU) 2019/1793.

- **Food Safety / Pesticide Residue Regime under Regulation (EU) 2019/1793 (as amended by Regulation (EU) 2026/194):**
  - *Applicability to BOTH Fresh and Frozen Strawberries:*
    - Commission Implementing Regulation (EU) 2026/194 (Recital 7 and Annex I) confirmed the inclusion of Egyptian strawberries under **both CN codes: `0810 10 00` (fresh or chilled) and `0811 10` (frozen)** in Annex I of Regulation (EU) 2019/1793.
    - *Hazard:* Increased frequency of official controls due to contamination risks by pesticide residues.
    - *EU Entry Clearance Document:* Mandatory pre-notification via **TRACES NT** using a **CHED-D** (Common Health Entry Document for Food of Non-Animal Origin) under Article 7 of Regulation (EU) 2019/1793 and Article 56(3)(d) of Regulation (EU) 2017/625.
    - *Clear Distinction Between Inspection Types and Frequencies:*
      - **Documentary Checks:** Conducted on **100% of consignments** under Article 54(1) of Regulation (EU) 2017/625 [Not verified from a saved primary text].
      - **Identity and Physical Checks:** Set at a single combined frequency of **20% of consignments** pursuant to **Article 6 of Regulation (EU) 2019/1793** and Annex I.
    - *Model Health Certificate Distinction:* Neither fresh nor frozen strawberries require an official model health certificate under Article 11 (which applies strictly to Annex II commodities).

- **Summary Comparison for Egyptian Strawberries:**
  - **Fresh Strawberries (`0810 10 00`):** Requires Phytosanitary Certificate (CAPQ) + CHED-PP (Plant Health under Reg 2016/2031 Art 72(1) & Reg 2019/2072 Annex XI Part A Point 5, subject to verification against current consolidated Annex XI) **AND** CHED-D (Food Safety under Reg 2019/1793 Annex I, with 100% documentary checks under Reg 2017/625 Art 54(1) [Not verified from a saved primary text] & a single combined frequency of 20% for identity and physical checks under Reg 2019/1793 Art 6).
  - **Frozen Strawberries (`0811 10`):** No general phytosanitary certificate requirement has been established based on the examined original 2019 Annex XI entries of Reg 2019/2072 (product classification, verification against current consolidated Annex XI, and any specific measures remain subject to `Requires human verification`), but **MANDATORILY REQUIRES CHED-D** (Food Safety under Reg 2019/1793 Annex I as amended by Reg 2026/194, with 100% documentary checks under Reg 2017/625 Art 54(1) [Not verified from a saved primary text] & a single combined frequency of 20% for identity and physical checks under Reg 2019/1793 Art 6).

### 2.3 Rules of Origin for Agricultural Products (Decision No 1/2024 of EU-Egypt Association Council)
- **Legal Reference:** Decision No 1/2024 of the EU-Egypt Association Council of 1 October 2024 replacing Protocol 4 (OJ L, 2024/2653, 9.10.2024; In force).
- **Rule for Chapter 8 (Oranges 0805 & Strawberries 0811):**
  - **NOT "Double Transformation".**
  - Annex II of Protocol 4 specifies for Chapter 8: *"Manufacture in which all the fruit, nuts and peels of citrus fruits or melons of Chapter 8 used are wholly obtained"*. [حقيقة مؤكدة من نص الملحق الثاني في القرار 1/2024].
  - Therefore, fresh oranges and frozen strawberries qualify for preferential tariff access under the **"Wholly Obtained"** rule (Article 3), meaning they must be grown and harvested in Egypt.
- **Proof of Origin Mechanism:**
  - Movement Certificate **EUR.1** issued upon application by the exporter.
  - Or an **Origin Declaration** typed on an invoice or commercial document:
    - Allowed for **any exporter** if the consignment value does not exceed **EUR 6,000** (Article 18(1)(b)).
    - Allowed for any value if made out by an **Approved Exporter** (Article 18(1)(a) & Article 19).
  - **Issuing Authority in Egypt:** According to Article 20(1) of the official text, movement certificates EUR.1 are issued by the **"customs authorities of the exporting Party"** (السلطات الجمركية المختصة). While local administrative procedures involve GOEIC in origin verification, the legally empowered authority in the treaty text is the Egyptian Customs Authority. Attributing issuance exclusively to GOEIC without citing a specific domestic decree is unverified. [Requires human verification].

---

## 3. Sector B: Textiles & Clothing (Garments, Fabrics, Children's Wear)

### 3.1 Ready-Made Garments & Fabrics (HS Chapters 61, 62, 50–60)
- **Trade Overview:**
  - Total Egyptian worldwide RMG exports estimated at ~$2.4–2.5 billion in 2023. [SUPPORTED FINDING / ESTIMATE: Egyptian Export Council figures; not verified against primary Eurostat Comext or UN Comtrade bulk datasets].
  - Key European retail buyers: Germany, Spain, Italy, Netherlands. [SUPPORTED FINDING / ESTIMATE: Secondary industry publications; not verified against primary Eurostat Comext database].

### 3.2 Rules of Origin for Textiles & Garments (Decision No 1/2024 of EU-Egypt Association Council)
- **Rules of Origin are product-specific and MUST NOT be generalized as a blanket "Double Transformation":**
  1. **Chapter 61 (Apparel and clothing accessories, knitted or crocheted):**
     - For garments obtained by sewing together or assembling pieces of knitted/crocheted fabric:
       *Rule:* **Knitting or crocheting combined with making-up including cutting of fabric.** [حقيقة مؤكدة: الملحق الثاني في القرار 1/2024].
     - For other knitted garments (e.g. seamless or knit-to-shape):
       *Rule:* Spinning of natural/man-made fibres combined with knitting/crocheting; OR extrusion of man-made yarn combined with knitting/crocheting; OR knitting and making-up in one operation.
  2. **Chapter 62 (Apparel and clothing accessories, not knitted or crocheted - Woven garments):**
     - General rule for ex Chapter 62:
       *Rule:* **Weaving combined with making-up including cutting of fabric; OR Making-up including cutting of fabric preceded by printing (as standalone operation).** [حقيقة مؤكدة: الملحق الثاني في القرار 1/2024].
       *(Note: The revised rules introduce a crucial alternative: printing accompanied by finishing operations followed by cutting/making-up, enabling origin without local weaving under specified conditions).*
     - Embroidered women's/girls'/babies' clothing (ex 6202, ex 6204, ex 6206, ex 6209, ex 6211):
       *Rule:* Weaving combined with making-up; OR manufacture from unembroidered fabric provided its value does not exceed 40% of the ex-works price.
  3. **Chapters 50 to 60 (Fabrics and intermediate textiles, e.g. Cotton Chapter 52):**
     - Cotton yarn (5204–5207): Spinning of raw fibres.
     - Cotton woven fabric (5208–5212): Weaving accompanied by dyeing, or yarn dyeing accompanied by weaving, or printing accompanied by preparatory/finishing operations.
- **Proof of Origin Requirements:**
  - Movement Certificate **EUR.1** issued by the customs authorities; OR
  - **Origin Declaration** by an Approved Exporter, or by any exporter for consignments up to **EUR 6,000** (Articles 18 & 19).

### 3.3 REACH & Chemical Substance Obligations (Regulation (EC) No 1907/2006)
- **Legal Status:** Active EU Regulation, binding on all articles placed on the EU market.
- **Critical Regulatory Distinction: Annex XVII vs. SVHC Obligations:**
  1. **Annex XVII Restrictions (Article 67):**
     - Mandatory statutory prohibitions or strict concentration thresholds. Non-compliant articles **cannot legally enter or be sold in the EU market**:
       - *Entry 43:* Azodyes releasing any of 22 restricted aromatic amines in concentrations > 30 mg/kg (0.003% w/w) in textiles having direct contact with skin.
       - *Entry 72 (Commission Regulation (EU) 2018/1513):* 33 CMR substances (Carcinogenic, Mutagenic, Reproductive toxicant Category 1A/1B) in clothing and related textiles. Strict substance-specific limits (e.g. formaldehyde 75 mg/kg, cadmium/lead 1 mg/kg, benzene 5 mg/kg).
       - *Entry 27:* Nickel release limits from metal components (buttons, zippers) touching the skin (< 0.5 µg/cm²/week).
       - *Entry 51/52:* Phthalates in plasticized textile components (0.1% cumulative limit for toys and childcare articles).
  2. **Candidate List Substances of Very High Concern (SVHC) Obligations:**
     - The presence of an SVHC on the Candidate List in a concentration **above 0.1% weight by weight (w/w)** does NOT constitute an automatic import ban. Instead, it triggers distinct statutory duties:
       - **Communication Duty (Article 33(1)):** Mandatory provision of safe use information (at minimum, the substance name) down the supply chain to industrial recipients, and to consumers upon request within 45 days (Art 33(2)).
       - **Notification to ECHA (Article 7(2)):** An EU importer must formally notify ECHA ONLY IF BOTH of the following conditions are met:
         (a) The SVHC concentration in the article exceeds 0.1% w/w, **AND**
         (b) The total quantity of that SVHC in the imported articles exceeds **1 tonne per year per importer**.
       - **SCIP Database Notification (Directive 2008/98/EC as amended by Directive (EU) 2018/851, Art 9(1)(i)):** EU suppliers must submit article data to ECHA's SCIP database for any article containing an SVHC > 0.1% w/w. Non-EU exporters must supply full composition data to their EU buyers.

### 3.4 Children's Clothing Standards & Legal Status under GPSR (Regulation (EU) 2023/988)
- **Legislation vs. Technical Standards Distinction:**
  1. **Binding Union Legislation:**
     - **General Product Safety Regulation (EU) 2023/988 (GPSR):** In force and applicable since 13 December 2024 (repealing Directive 2001/95/EC per Article 50(1)). Mandates that all consumer products placed on the EU market must be safe (Article 5), accompanied by technical documentation (Articles 9 & 10), traceable labelling (Article 9(5)), and an EU Responsible Economic Operator for non-EU imports (Article 16). [VERIFIED FACT: CELEX 32023R0988].
  2. **Harmonised Standards vs. Industry Technical Standards Analysis:**
     - **Legal Presumption of Conformity Mechanism (Article 7 vs. Article 8 of GPSR):**
       - Under **Article 7(1)(a) of GPSR**, a presumption of conformity with the general safety requirement arises *only* when a product conforms to European standards "the references of which have been published in the Official Journal of the European Union in accordance with Article 10(7) of Regulation (EU) No 1025/2012".
       - Under **Article 8(1)(a) of GPSR**, in the absence of standards published under Article 7(1)(a), market surveillance authorities assess product safety taking into account European standards *other than those referred to in Article 7(1)(a)*, international standards, and industry good practices.
     - **EN 14682:2014** (*Safety of children's clothing - Cords and drawstrings on children's clothing - Specifications*):
       - *Factual Listing:* "EN 14682:2014 is listed in Annex I, Entry 37, of Commission Implementing Decision (EU) 2026/901." [VERIFIED FACT: Exactly quoted from OJ L, 2026/901, 27.4.2026].
       - *Publication in the Official Journal (Article 1):* Article 1 of Decision (EU) 2026/901 explicitly provides that: *"The references to European standards for products drafted in support of Regulation (EU) 2023/988, listed in Annex I to this Decision, are hereby published in the Official Journal of the European Union."*
       - *Legal Consequence under Article 7(1)(a) GPSR:* "Conformity gives rise to a presumption of safety under Article 7(1)(a) of Regulation (EU) 2023/988, limited to the risks and risk categories covered by the standard. It does not establish overall product compliance."  
         *Status of Interpretation:* [Agent's reading of the primary text, pending qualified human expert review].
       - *Voluntary Nature & Scope Limitation:* EN 14682:2014 is a voluntary technical standard (not a mandatory regulation), and conformity with it creates an evidentiary presumption of safety strictly for the mechanical hazards covered (cords and drawstrings); it does not prove overall product compliance or safety against other applicable Union rules (e.g. chemical restrictions under REACH Annex XVII, flammability, etc.).
       - *Attribution of 13 December 2024 Date:* In the European Commission's official summary list of European standards supporting Regulation (EU) 2023/988 (SummaryListForLegislation_1010211, generated 27 April 2026), the "start of effect" date for EN 14682:2014 is attributed as **13 December 2024** (with publication reference OJ C 335, 09.10.2015). The summary list is published for information purposes only and does not itself generate legal effects.
       - *Unresolved Expert-Review Question:* *"What was the legal status of EN 14682:2014 between 13 December 2024 and publication of Commission Implementing Decision (EU) 2026/901 on 27 April 2026?"* (Left open without assumption for qualified legal review).
       - *Substantive Technical Scope:* Prohibits drawstrings/functional cords in the hood and neck area for young children (under 7 years), and regulates cord lengths, loops, and toggles for older children (up to 14 years).
     - **EN 17394 Series** (*Safety of children's clothing - Security of attachment of buttons and small parts*):
       - *Exact Limited Status:* "No entry identified in Annex I or Annex II of Decision (EU) 2026/901 or in the Commission summary list generated on 27 April 2026. Absence from the whole Official Journal publication history was not established."
       - *Part 3 Designation (EN vs. CEN/TS):* The Part 3 designation (EN vs CEN/TS) remains unresolved. No official CEN or Official Journal evidence inspected in this research round establishes the correct designation. 
       - *Status under GPSR:* Because they are not listed in Annex I or II of Decision (EU) 2026/901, these examined parts do not confer a presumption of conformity under Article 7(1)(a) of Regulation (EU) 2023/988 on the basis of that Decision. They may be considered by market surveillance authorities under Article 8(1) of GPSR as non-harmonised European standards, technical specifications, or industry codes of good practice. [VERIFIED FACT].

---

## 4. Current Compliance Workflows & Operational Pain Points
- Egyptian SME exporters operate largely on a reactive, manual compliance model:
  1. **Buyer-Driven Specifications:** Product requirements, label layouts, and chemical RSL (Restricted Substances Lists) are received as buyer purchase order conditions rather than researched independently.
  2. **Fragmented Testing:** Pre-shipment batch testing (pesticide multi-residue analysis for produce, azo dye / formaldehyde testing for garments) is outsourced to commercial labs (QCAP, CAPL, SGS, Intertek, Bureau Veritas). Turnaround times and testing costs represent recurring operational friction.
  3. **Lack of Automated Regulatory Tracking:** Exporters lack automated alerting when EU regulations change (such as Regulation 2026/194 shifting inspection frequencies, or REACH updating Annex XVII / Candidate List).
  4. **Document Dossier Mismatches:** Errors in origin documentation (confusion over wholly obtained vs. double transformation rules, incorrect EUR.1 boxes, or lack of Approved Exporter status for invoices > €6,000) lead to customs delays, lost preferential tariff treatment, or port demurrage. [استنتاج تحليلي مستند للمراجعة التنظيمية؛ يتطلب التحقق بمقابلات عملاء فعلية في Phase 0A/Founder Action].

---

## 5. Future Markets Note (US, UK, GCC)
The United States represents a mature export channel for Egyptian ready-made garments under the QIZ duty-free protocol, but features distinct regulatory obligations (US CPSC, FDA, UFLPA). The United Kingdom operates under a post-Brexit bilateral agreement with standards largely derived from the EU acquis but diverging administratively. The GCC (notably Saudi Arabia and the UAE) constitutes Egypt’s largest regional trading partner for fresh agri-produce and home textiles, governed by SFDA and GSO standards. While these three markets offer substantial expansion potential, their distinct jurisdictional frameworks dictate that they remain out of MVP scope for Phase 0 and Phase 1. [توصية وتفسير].

---

## 6. Verification Ledger

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
| `https://eur-lex.europa.eu/eli/dec_impl/2026/901/oj` | **نعم** (HTTP 200 OK) | فحص القرار التنفيذي 2026/901 وقوائم معايير GPSR (الملحق I، البند 37) | 2026-11-07 | Active (نافذ من 27-04-2026) |
| `https://single-market-economy.ec.europa.eu/single-market/goods/european-standards/harmonised-standards/general-product-safety_en` | **نعم** (HTTP 200 OK) | تنزيل وفحص القائمة التلخيصية الرسمية لمعايير GPSR (ملف PDF/XLSX المؤرخ 27-04-2026) | 2026-11-07 | Active (قائمة المفوضية الرسمية) |
| `https://trade.ec.europa.eu/access-to-markets/en/home` | **نعم** (HTTP 200 OK) | فتح مباشر للواجهة العامة (لم تُختبر API) | 2026-11-07 | Active (بوابة التجارة العامة) |
| `https://www.efsa.europa.eu/en` | **نعم** (HTTP 200 OK) | فتح مباشر للواجهة العامة (لم تُختبر API) | 2026-11-07 | Active (الهيئة العلمية لسلامة الغذاء) |
| `https://food.ec.europa.eu/plants/pesticides/eu-pesticides-database_en` | **نعم** (HTTP 200 OK) | فتح مباشر للواجهة العامة (لم تُختبر API) | 2026-11-07 | Active (قاعدة المبيدات بالمفوضية) |
| `https://echa.europa.eu/` | **لا** (حظر 403) | محاولة اتصال مباشر صُدّت بواسطة WAF | 2026-11-07 | Active (تعذر الفحص الآلي المباشر) |
| `https://comtradeplus.un.org/` | **لا** | ملخص بحث ثانوي (غير مفتوح) | 2026-11-07 | غير مُتحقَّق منه بالكامل |
| `https://ec.europa.eu/eurostat` | **لا** | ملخص بحث ثانوي (غير مفتوح) | 2026-11-07 | غير مُتحقَّق منه بالكامل |
| `https://webgate.ec.europa.eu/rasff-window/` | **لا** | ملخص بحث ثانوي (غير مفتوح) | 2026-11-07 | غير مُتحقَّق منه بالكامل |
| `https://goeic.gov.eg/` | **لا** | ملخص بحث ثانوي (غير مفتوح) | 2026-11-07 | غير مُتحقَّق منه بالكامل |
| `https://capq.gov.eg/` | **لا** | ملخص بحث ثانوي (غير مفتوح) | 2026-11-07 | غير مُتحقَّق منه بالكامل |

---

## 7. Mandatory Report Disclaimer
"This report provides regulatory research and compliance-support information based on the sources and product information available at the time of generation. It is not an official government approval, certification, legal opinion or guarantee of market access. Requirements should be verified with the relevant authorities and qualified professionals."
