# Expert Deep Research Report: Indian Agricultural Procurement-Centre Inefficiencies
**Prepared by:** Expert Agricultural Supply Chain Researcher, E-Governance Analyst, and SIH Product Strategist  
**Date:** 2026-08-27  

---

### EXECUTIVE SUMMARY
This report presents a rigorous, evidence-based investigation into the systemic operational and technical inefficiencies plaguing agricultural procurement centres (mandis) in India. Drawing heavily from Comptroller and Auditor General (CAG) performance audits, NITI Aayog evaluations, and primary academic literature, we bypass e-governance public-relations rhetoric to expose the structural bottlenecks in crop procurement, slot booking, and direct payments. 

Our core finding is that **digitisation has decoupled administrative targets from physical and operational capacities**, creating new forms of digital exclusion, systemic fraud, and yard congestion. Rather than optimizing a broken static scheduling model, this report outlines the **"MandiQ" Blueprint**—a truly offline-first, dynamic queue management framework designed to solve the genuine whitespace of mandi logistics and empower India's smallholder farmers.

---

### PHASE 1: PROBLEM VALIDATION & SOURCE SYNTHESIS

#### 1.1 The Ground Truth: Root Causes of Procurement Delays
State-level and national performance audits reveal that the primary driver of agricultural procurement delays is the **operational decoupling of crop arrivals, physical yard clearance (lifting), and payment processing workflows** [46, 47]. Public platforms often market digital portals as end-to-end solutions, but physical and structural asset mismatches systematically stall mandi operations:

*   **Lifting and Transport Bottlenecks:** When state agencies fail to coordinate immediate transport of weighed grain from mandi yards to warehouses or custom millers, physical yards become saturated [47]. Arriving farmers are forced to wait for extended periods in adjacent yards or access roads [47].
    *   *Audit Evidence:* The CAG's 2023 Performance Audit (Report No. 20) on FCI Storage Management highlights a massive shortfall in foodgrain movement (ranging from **46% to 60%** relative to procurement and **17% to 19%** relative to planned movement) due to railway rake shortages and lack of inter-departmental coordination [76, 83]. This directly causes grain accumulation at the mandis.
*   **Storage Capacity Constraints:** Primary Agriculture Credit Co-operative Societies (PACS) lack adequate covered storage, forcing unscientific open-air Covered and Plinth (CAP) storage [48, 78].
    *   *Audit Evidence:* In Jharkhand (JSFCL, 2025 Audit), PACS could only procure 16.47 lakh MT against an 18.29 lakh MT target due to a lack of cash credit lines, limited storage, and millers defaulting on custom milling [26, 48, 181]. In Punjab, open CAP storage damaged **19,084 MT** of wheat (acquisition cost of **₹40.25 crore**), with **78% (₹31.60 crore)** of the damage occurring specifically due to poor preservation in SGA open plinths [69].
*   **Avoidable Financial Carryover:** In Punjab and Haryana, the FCI incurred **₹170.26 crore** in avoidable Carryover Charges paid to State Government Agencies (SGAs) because it failed to direct SGAs to deliver wheat to available vacant covered storage [65, 66].
*   **Capital Block and Target Deficits:** In Madhya Pradesh (MPSCSC), excess procurement blocked **₹176.01 crore** in capital and caused **₹114.40 crore** in damaged paddy stock due to unscientific storage and delayed lifting [48, 49]. In Telangana, a rabi season target of 90 lakh MT achieved only 46.21 lakh MT of procurement, leaving a **payment deficit of over ₹13,000 crore** due to gunny bag shortages and a slow milling network [48, 258].

#### 1.2 The Farmer Journey: Physical and Digital Friction Points

```
[1. Online Registration] ──> [2. Slot Booking] ──> [3. Mandi Arrival] ──> [4. Quality Check] ──> [5. Weighment] ──> [6. Billing] ──> [7. DBT Payout]
       │                            │                     │                     │                   │               │               │
       ▼                            ▼                     │                     │                   │               │               ▼
 Mismatch Errors              OTP Timeout /               ▼                     ▼                   ▼               ▼         Delayed Days to
 tenant exclusion              DBT locks             3-4 Hr Queue          Name-Only Assay     Manual overrides  G/J-Form Lags    Weeks; Decoupled
  (40-50% tenant)                                    Biometric Fail         Cartelization       Server Downtime                    from lifting
```

1.  **Online Registration:** Farmers register personal, land, and banking details online (e.g., on Haryana's *Meri Fasal Mera Byora - MFMB* or MP's *e-Uparjan*) [28, 95]. Land records are digitally verified to confirm authenticity [10].
    *   *Friction Point:* Discrepancies such as misaligned plot boundaries, tenant verification failure, or incorrect crop classifications systematically prevent farmers from booking slots [51]. Gurnam Singh Chaduni-led BKU documented that **60% of Haryana's farmers** faced severe name or area mismatch errors [6, 9].
    *   *Tenant Exclusion:* Informal tenancy is highly prevalent in Punjab (40-50% of farmers lease land informally) [241, 315]. Because tenant farmers cannot provide formal land records (with land leasing being legally unrecorded), they are excluded from registering on the *Anaaj Kharid* portal, barring them from direct MSP payments and forcing them to sell to private traders at steep discounts [241, 315].
2.  **Slot Booking:** Once registered, the farmer must book an arrival slot on the state portal (e.g., Rabi slot booking on e-Uparjan) [87].
    *   *Friction Point:* The portals frequently fail during peak harvest windows due to concurrent traffic spikes [50]. Authentication interfaces timeout during multi-factor authentication (MFA); OTP delivery lags cause sessions to expire [51, 59]. Database locking bugs often clear the selected slot without generating a reference ID, forcing the farmer to restart [51, 59].
3.  **Arrival & Gate Check-In:** The farmer transports the produce to the assigned procurement centre [17].
    *   *Friction Point:* Farmers experience chaotic mandi gridlock, driving long distances (e.g., Veer Singh driving 32 km to Karnal NH-44 mandi) only to queue for **3 to 4 hours** for a gate pass [34, 35]. Mandatory Aadhaar-enabled biometric POS verification introduces a severe hurdle for older agricultural laborers: decades of manual labor wear down fingerprints, leading to persistent thumb matching failures at the entry gates [52, 241].
4.  **Quality Assaying:** Mandi officials or third-party labs draw samples for quality checks [88, 247].
    *   *Friction Point:* On-site assaying units are poorly equipped and slow, leading to long idle times [191, 192]. Studies on e-NAM in Guntur APMC show that **60.83% of farmers** perceived quality assaying as non-functional [192]. Because both farmers and traders lack confidence in the digital assaying reports, local traders rely strictly on physical inspection, turning digital assay entries into "namesake" compliance records [196, 205]. This enables **trader cartelization (80.83% constraint)**, where traders pre-fix bidding prices below MSP [192, 195].
5.  **IoT Weighment and Grading:** Once graded, vehicles proceed to the weighbridge [17].
    *   *Friction Point:* Traditional weighbridges are prone to manual tampering and under-weighment [35]. While Bluetooth-enabled digital scales prevent manual override by writing directly to the server, server outages during peak windows disconnect weighbridge integrations, forcing officials to resort to manual, unvalidated entries that bypass fraud-detection rules [23, 51, 236].
6.  **Billing & On-the-Spot Receipting:** The system compiles weight and grade to generate a digital sale receipt (J-Form in Haryana) and transit pass [17, 97].
    *   *Friction Point:* Lags in G-form and J-form generation occur frequently due to unstable rural network connectivity, causing transactions to time out [52, 236].
7.  **Direct Bank Payout (DBT):** The portal initiates direct payment via the National Payments Corporation of India’s (NPCI) Aadhaar Payment Bridge (APB) to the farmer's seeded bank account [20, 22].
    *   *Friction Point:* Despite a statutory **72-hour payment mandate** (e.g., Haryana e-Kharid) [25], payments are routinely delayed by weeks or months. In Jharkhand, the first payment installment was delayed by **up to 775 days**, and the second by **up to 370 days** [48, 181]. In Telangana, billions of rupees in payments were frozen [48, 258]. This is because state guidelines often mandate that payments are only processed *after* the custom miller confirms the physical receipt of grain (TP-cum-AC Note), thus tying financial settlements to transport and lifting efficiency rather than weighment completion [47, 246, 248].

#### 1.3 Contradictory Evidence: The Fallacy of "Digitisation Solves Everything"
The transition to digital-first agricultural procurement has introduced severe operational vulnerabilities, digital exclusion, and high-tech corruption:

*   **Older Laborer Exclusion:** Worn-down fingerprints of agricultural laborers lead to biometric POS authentication failures at gate entry and weighbridges, completely blocking legitimate sales [52, 241].
*   **Systemic Portal Frauds & Payment Diversions:** Digital centralization has created high-yield targets for cybercriminals. In late 2024, the Punjab Police Cybercrime Division uncovered a massive scam on the *Anaaj Kharid* portal [237]. Fraudsters compromised administrative credentials, used unauthorized OTP overrides via burner phones bought on fake IDs, and altered farmers' registered bank details [237, 251, 253]. Payments were redirected to synthetic bank accounts, and the fraudsters restored the original bank profiles immediately after payout confirmation to avoid detection [237, 238, 252]. This forced the state to freeze payouts, locking up over **₹4.36 crore** of legitimate trade funds [238, 251].
*   **Acreage and Yield Suppression (Database Manipulation):** In Haryana, database manipulation triggered major farmer protests. Union leaders filed formal complaints alleging that verified crop yields and paddy acreages on the *Meri Fasal Mera Byora (MFMB)* database were altered or suppressed [239]. This database manipulation artificially reduced the volume of crops a farmer was digitally authorized to sell, leading to a suspected **₹5,000 crore procurement scam** to prevent farmers from claiming MSP [239].
*   **Mandi Level Grievance Void:** When e-governance systems glitch (e.g., during the e-Kharid server outage in Karnal), there is no direct, real-time grievance redressal mechanism or troubleshooting dashboard at the mandi level [51, 105]. Farmers must sit in tractors for hours without food or rest, and officials are forced to bypass digital rules entirely to prevent physical gridlock [35, 51].

---

### PHASE 2: EXISTING SYSTEMS & COMPETITIVE LANDSCAPE

#### 2.1 Inventory of Current Infrastructure

*   **Government Mandi Portals (e-NAM):** A pan-India electronic trading portal integrating 1,389 APMC mandis [154, 320]. It features online auctions, digital assays, and direct bank settlements [154, 321]. However, interstate trade remains low, traders cartelize in private auction loops, and payment clearance takes at least 1–2 business days compared to cash [159, 192, 198].
*   **State Procurement Systems (e-Kharid, MP e-Uparjan, Odisha P-PAS):** These automate regional APMC mandi operations [28, 97, 222]. e-Kharid automates gate passes and J-forms [97]; e-Uparjan tracks crop declaration to JIT payments [88, 222]; P-PAS handles land-record cross-verification and advance tokens [18, 247]. These represent state-of-the-art administrative portals but are plagued by MFA timeouts, database locks, and lack of real-time queue management [51, 59].
*   **Primary Agricultural Credit Societies (PACS):** Act as localized procurement agents at the village level [48, 305]. Despite national computerisation drives, PACS suffer from limited storage and restricted cash-credit lines, creating local procurement stoppages [48, 181].
*   **Agritech Startups:**
    *   *Agribazaar, ApnaGodam, Arya.ag:* Offer private e-warehousing, digital commodity financing, and private online mandis [18, 38, 154].
    *   *TraceX & Organic India:* Implement Bluetooth-enabled digital scale integration and geotagged farm mapping, achieving 80% faster procurement cycles [18].
    *   *GrainFlow (US/Canada):* Employs computer-vision yard intelligence and AI-scheduling to target grain elevator gridlock [18, 221].

#### 2.2 The "Do NOT Claim as Unique" List
The following features are **fully solved and standard in India**. An SIH team claiming these as "novel" will be immediately dismissed by expert evaluators:

1.  **Farmer Online Registration & Land Record Verification:** Already implemented at scale by Haryana's MFMB [25], MP's e-Uparjan [37], and Odisha's P-PAS [18]. Land ownership is auto-verified against state registries to block fraudulent claims [10, 28].
2.  **Day-Level Slot Booking / Advance Tokens:** Already implemented in Chhattisgarh's UPAHAR system (dynamic tokens with date, time, and allowable quantity limits) [64] and e-Uparjan's Farmer Slot Booking Rab/Kharif portal [87].
3.  **Standard SMS Alerts & Multilingual Push Notifications:** MP's e-Uparjan SMS service provider RFP details a functional requirement for sending over **20 crore transactional SMS** annually in Hindi and English with full DLT sender-ID registration [130, 137].
4.  **Aadhaar-Seeded Direct Benefit Transfer (DBT):** Odisha's P-PAS is fully integrated with the Public Financial Management System (PFMS) for direct payment [247]; MP e-Uparjan utilizes JIT ePayments integrated with the Aadhaar Payment Bridge (APB) [37, 222].

#### 2.3 Static vs. Real-Time Queuing: Technical Comparison
Current government portals utilize **Static Scheduling**, whereas industrial logistics use **Real-Time Dynamic Scheduling**. 

```
STATIC SCHEDULING (Current Portals)
[Farmer Books Slot: "Oct 5, 10 AM - 12 PM"] ──> Mandi Weighbridge Breaks Down ──> [Result: Multi-Hour Tractor Jam / Gridlock]

REAL-TIME DYNAMIC SCHEDULING (INFORM / Proposed MandiQ)
[Weighbridge Speed Slows (Camera Detects Queue)] ──> [Score recalculated: S_i] ──> [Reschedule advice sent to un-departed farmers]
```

| Technical Dimension | Static Scheduling (MP e-Uparjan, Haryana e-Kharid, UPAHAR) | Real-Time Dynamic Scheduling (INFORM, GrainFlow, Proposed MandiQ) |
| :--- | :--- | :--- |
| **Scheduling Core** | Theoretical hourly capacity limits set on paper (e.g., maximum 50 tokens per hour) [64, 87]. | Constrained optimisation based on live weighbridge throughput, gate arrivals, and yard clearances [144, 145]. |
| **Handling of Disruptions** | Zero. If a weighbridge fails or custom millers delay lifting, slots remain unchanged, leading to traffic jams [51, 146]. | High. System automatically recalculates capacity constraints and dynamically updates priorities [146, 227]. |
| **Queue Prioritization** | First-Come, First-Served (FCFS) based strictly on physical gate arrival, leading to morning rush-hour bottlenecks [146, 147]. | Multi-criteria Priority Score ($S_i$) computed dynamically, factoring in on-time adherence, crop quality, and waiting time [147, 148]. |
| **Transit Awareness** | None. The system is unaware if the farmer has broken down on the road or hasn't left the farm yet [146]. | High. Computes ETA projections and triggers proactive rescheduling suggestions to farmers prior to departure [149, 226]. |
| **Hardware & IoT Linkage** | Disconnected. The portal is independent of physical gate sensors or weighbridge telemetry [256]. | Connected. Integrated with computer-vision queue counters, RFID gate passes, and Bluetooth scales [17, 149]. |

---

### PHASE 3: GAP ANALYSIS & FAILED ATTEMPTS

#### 3.1 The Gap Matrix: Unsolved Problems Categorized by Severity

| Severity Level | Problem Domain | Target Audience | Primary Technical / Operational Bottleneck | Key Source Evidence |
| :--- | :--- | :--- | :--- | :--- |
| **Level 1: Already Solved** | Online Farmer Registration & Land record verification. Direct bank account mapping. | Land-owning farmers, cooperative administrators. | Fully completed via state land record integrations (e.g., e-Kharid, P-PAS, e-Uparjan) [10, 28, 97]. | [10, 25, 28, 37] |
| **Level 2: Partially Solved** | Digital weighing scale integration. Day-level token scheduling. | Mandi weighbridge operators, logistics teams. | Standardized Bluetooth scale hardware exists but lacks offline transaction logic and central registry synchronisation [18, 51, 236]. | [18, 23, 64] |
| **Level 3: Mostly Unsolved** | Same-Day DBT settlement. Credible Automated Quality Assaying. | Smallholders, APMC traders, millers. | DBT is delayed because state portals decouple financial triggers from weighment, waiting for custom miller lifting confirmation [47, 248]. Assaying is manual and collusive [196, 210]. | [3, 48, 192, 202] |
| **Level 4: Completely Unsolved** | **1. Offline-First Mandi Transaction Engine.**<br>**2. Dynamic Multi-Criteria Queue Optimization.**<br>**3. Tenant/Sharecropper Verification.**<br>**4. Payment Audit Cryptography.** | Smallholder farmers, tenant farmers, mandi board cyber-security cells, transporters. | **1.** Portals freeze during network drops; manual overrides bypass security [51, 236].<br>**2.** Mandis lack real-time priority queues, creating starvation [147, 148].<br>**3.** Tenants have no formal lease records [241, 315].<br>**4.** Portals lack secure cryptographic audit trails on bank detail edits [237]. | [51, 147, 236, 237, 241] |

#### 3.2 Failure Analysis of Past Procurement Technologies
Why have prior attempts at mandi queue management and scheduling glitched in India?

1.  **The "Live-Internet Dependency" Flaw (e-Kharid Outages):**
    Mandi systems are designed as cloud-dependent web applications [330]. During peak procurement season, peak traffic collapses the servers [50]. In the Karnal mandi outage (April 2026), e-Kharid servers went offline, entry gates could not generate passes, and Bluetooth scales could not sync [34, 51, 236]. To prevent physical vehicle gridlock, mandi officials bypassed the digital portals and issued manual gate passes [34, 51, 236]. This bypassed the automated validation rules, creating massive data reconciliation gaps between gate entry logs and transaction records [51, 236].
2.  **The "Rigid MFA and Database Locking" Flaw (e-Uparjan Timeouts):**
    In Madhya Pradesh, the e-Uparjan slot booking portal frequently crashes during peak hours [51]. The system uses standard multi-factor SMS authentication [87]. Under heavy telecom loads, OTP delivery lags cause the browser session to time out [51, 59]. When the portal writes a slot booking back to the central land database, database locking issues clear selected slots without generating a confirmation reference ID, leaving farmers with incomplete transactions [51, 59].
3.  **The "Aadhaar Seeding and OTP Override" Security Breach (Anaaj Kharid Fraud):**
    The Punjab Anaaj Kharid portal relied on basic session tokens and weak multi-tier validation [237]. Cybercriminals exploited this by compromising credentials of local mandi operators, overriding OTP validation on burner phones, and updating legitimate farmers' profiles with synthetic bank accounts [237, 252]. Because the portal lacked a cryptographic ledger of changes or a dual-signature approval process for bank updates, the fraud went unnoticed until multiple farmers complained of zero payments [251, 253].
4.  **The "Informal Tenancy Void" (Exclusion of Sharecroppers):**
    Portals like Anaaj Kharid require mandatory land record linking to verify ownership [115, 312]. However, 40-50% of Punjab's cultivation is conducted under informal, unrecorded leases [241, 315]. While Haryana allows a written lease-deed undertaking [315], Punjab tenants lack formal records and cannot book slots [241, 315]. They are forced to sell their crops to unlicensed arhtiyas below MSP [241].

#### 3.3 True Whitespace: Where is the SIH Product Opportunity?
The genuine whitespace in agricultural procurement comprises four unaddressed, fragmented capabilities:

1.  **Cryptographically Signed Offline-First Mandi Transaction Log:**
    A localized, edge-computing mandi node that continues to register arrivals, verify farmer codes offline, capture Bluetooth weights, and generate local cryptographically signed tokens (HMAC-SHA256) even when internet is completely down.
2.  **Dynamic Priority-Score ($S_i$) Rules-Based Queue Controller:**
    An active queue engine that sequences physical trucks dynamically at the gate, preventing starvation using actual waiting penalties while prioritizing high-moisture perishable crops to prevent post-harvest spoilage.
3.  **Low-Bandwidth Zero-Internet USSD/SMS Interactive Slot Portal:**
    A communication gateway that uses mobile signaling networks (USSD MAP layer) instead of mobile data, allowing low-literacy farmers on feature phones to query live wait times, check prices, and reschedule slots instantly.
4.  **Computer-Vision Edge-AI & IoT Weighbridge Synced Yard Management:**
    Automated cameras at mandi ramps that continuously count physical queues and monitor gate-to-dock dwell times, integrating with the scheduling core to trigger proactive "delay departure" alerts to farmers.

---

### PHASE 4: THE SIH BLUEPRINT (WHAT WE SHOULD BUILD)

#### 4.1 Core Innovation: The **MandiQ** Platform
We propose **MandiQ**—a decentralized, offline-resilient, dynamic queue management and tamper-proof payment authorization system for agricultural procurement yards. MandiQ integrates edge computing, multi-criteria mathematical scheduling, IoT weighbridge telemetry, and a zero-data cellular interface (USSD) into a single interoperable node.

```
                  ┌────────────────────────────────────────────────────────┐
                  │                 CENTRAL GOVT PORTAL / CLOUD            │
                  └───────────────────────────┬────────────────────────────┘
                                              │ Sync (OpenSync Protocol)
                                              ▼ [Compressed JSON Batches]
                  ┌────────────────────────────────────────────────────────┐
                  │               MandiQ LOCAL EDGE GATEWAY                │
                  │        [SQLite Database, AES Cryptographic Sign]       │
                  └──────┬────────────────────┬────────────────────┬───────┘
                         │                    │                    │
                         ▼                    ▼                    ▼
               ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
               │    GATE ENTRY    │ │   WEIGHBRIDGE    │ │   USSD FALLBACK  │
               │   [Biometric &   │ │   [Bluetooth-    │ │  [GSM MAP Layer, │
               │   RFID Kiosk]    │ │  Direct Scale]   │ │   No Internet]   │
               └──────────────────┘ └──────────────────┘ └──────────────────┘
```

#### 4.2 Technical Novelty vs. Product Novelty

*   **Technical Novelty (The Algorithmic Core):**
    1.  *Multi-Criteria Dynamic Prioritization:* At gate check-in, trucks are re-sequenced in the active queue based on a dynamic Priority Score ($S_i$) calculated in real-time [147]:
        $$S_i = \alpha \cdot A_i + \beta \cdot D_i + \gamma \cdot Q_i + \lambda \cdot W_i$$
        *   $A_i$ (Appointment Adherence, Max 40 points): Points are deducted if a truck is late to its static slot, protecting on-time flows [148].
        *   $D_i$ (Demurrage & Contractual Weight, Max 20 points): Prioritizes high-capacity commercial carriers [148].
        *   $Q_i$ (Crop Quality & Moisture Risk, Max 20 points): Dynamically prioritizes wet crops (e.g., high-moisture paddy detected during assaying) to prevent spoilage [148].
        *   $W_i$ (Dynamic Wait-Time Penalty, Max 20 points): Computed as $W_i = \min(20, \mu \cdot t_{wait})$ [148]. As physical wait time ($t_{wait}$) increases, the priority of delayed trucks rises automatically, preventing queue starvation [148, 228].
    2.  *Cryptographic Offline-First Synchronization (OpenSync):* MandiQ operates locally on edge hardware with a SQLite database [327]. When the central server drops, MandiQ continues transactions, signing every entry with a local hardware security module (HSM) [2, 327]. Upon reconnection, the *OpenSync* protocol compresses transactions into under-100KB gzip batches and reconciles them using conflict-resolution rules [327, 332].
    3.  *Double-Signature Payment Auditing:* Any change to a farmer's registered bank profile requires a biometric match on-site at a kiosk or a physical dual-sign-off from the Cooperative Society Secretary and the District Manager, cryptographically locked on a distributed ledger to eliminate Anaaj Kharid-style bank diversion frauds [2, 237].
*   **Product Novelty (Operational Fallback):**
    *   *Zero-Data USSD Interface:* By dialing a shortcode (e.g., `*123#`), farmers use the operator's GSM MAP layer (which operates without mobile data or internet) to view crop prices, query payment status, and interactively reschedule slots via simple text menus [19, 150, 172].
    *   *Edge Automated Dwell Tracking (Phase 2 Vision):* In enterprise deployment, high-angle optical gate sensors can count incoming tractors, compute queue depth, and broadcast departure-delay SMS alerts to farmers who have not yet left their farms (deferred to Phase 2 per ADR-003; prototype computes queue depth deterministically from gate QR check-ins and Redis ZSET tracking) [4, 149].

#### 4.3 SIH Prototype Feasibility and Data Strategy

*   **Public Datasets to Leverage:**
    1.  *AgriStack (India Digital Ecosystem):* API sandbox to simulate verified land holdings and farmer identities [5].
    2.  *AGMARKNET API:* Daily price data to populate the dynamic USSD pricing board [168].
    3.  *IMD weather data:* Real-time regional rainfall feeds to dynamically adjust the $Q_i$ moisture priority score in case of heavy downpours [128, 148].
*   **What to Simulate/Mock for the SIH Prototype:**
    *   *UIDAI Aadhaar API:* A mock server to simulate biometric authentication, biometric mismatches, and OTP timeouts [51, 52].
    *   *PFMS / NPCI Aadhaar Payment Bridge:* Mock API endpoints to simulate same-day settlement trigger events and profile alter-alerts [20, 247].
    *   *Bluetooth Weighscale Telemetry:* A simple Python socket server emulating live weight data transfer to the local edge node.

#### 4.4 Measurable KPIs for Evaluation
To prove MandiQ's efficacy during the SIH finale, we will track the following:

1.  **Reduction in Average Turnaround Time (TAT):** Average vehicle wait time from gate entry to weighment release reduced by **$\ge 75\%$** (targeting $\le 45$ minutes vs. traditional 3-4 hours) [34, 149].
2.  **Queue Smoothness / Congestion Index:** Standard deviation of hourly vehicle arrivals minimized relative to the mandi's physical capacity limit ($C_{max}$) [144, 145].
3.  **Data Synchronization Integrity:** Zero transaction losses, zero duplicate profiles, and 100% cryptographic validation rate of offline transactions upon central server reconnection [13, 348].
4.  **Transaction Accessibility Rate:** System availability maintained at **$\ge 99.9\%$** in low-connectivity zones via USSD/Offline fallback (an 87% improvement in service reliability) [121, 345].

---

### PHASE 5: ACTIONABLE RESEARCH EXPANSION

#### 5.1 Master Source Table (Top 15 Credible References)

| Sl. No. | Organization / Source | Year | Key Operational Finding | Reference / URL |
| :--- | :--- | :--- | :--- | :--- |
| **1** | Comptroller and Auditor General (CAG) of India | 2023 | Report No. 20: Avoidable Carryover Charges of ₹170.26 crore paid to SGAs due to unutilized vacant warehouse capacity; short-despatches ex-Punjab led to ₹182.29 crore in excess storage fees. | [CAG Report No. 20 of 2023](https://cag.gov.in/uploads/download_audit_report/2023/Report-No.-20-of-2023_PA-on-FCI_English-PDF-A-066b9d3c33f4c35.05840530.pdf) [53] |
| **2** | Comptroller and Auditor General (CAG) of India | 2015 | Report No. 31: Delivery defaults of Custom Milled Rice (CMR) worth ₹7,570.78 crore in AP/Telangana; documented transport logging frauds involving invalid vehicles (motorcycles, auto-rickshaws) in UP and Bihar. | [CAG Report No. 31 of 2015](https://www.scribd.com/document/723472132/5-CAG-Report-No-31) [53] |
| **3** | International Journal of Political Science and Governance | 2024 | Empirical study of e-Kharid in Haryana: Documented how portal outages, biometric errors, and decoupling of crop lifting systematically violate the 72-hour direct-payment mandate. | [ResearchGate Publication](https://www.researchgate.net/publication/393859399_Digitising_agriculture_procurement_in_Haryana_An_empirical_study_of_Meri_Fasal_Mera_Byora_and_E-Kharid_Portal) [53] |
| **4** | Comptroller and Auditor General (CAG) of India | 2025 | Procurement Activity of JSFCL: Documented major delays in MSP disbursement, with the first installment delayed by up to 775 days and the second by up to 370 days. | [CAG Jharkhand Executive Summary](https://cag.gov.in/uploads/download_audit_report/2025/2-Executive-Summary-069b9349fb47d19.49082624.pdf) [53] |
| **5** | Comptroller and Auditor General (CAG) of India | 2011 | Performance Audit of Pungrain (Punjab): Open storage forced by 66% to 82% storage deficit damaged 18,272 MT of wheat (₹18.41 crore loss); delays of up to 125 days in preparing sale bills caused interest losses. | [CAG Punjab Commercial Audit](https://saiindia.gov.in/uploads/download_audit_report/2011/Punjab_Commercial_2011_Overview.pdf) [53] |
| **6** | Comptroller and Auditor General (CAG) of India | 2017 | Working of MPSCSC: Excess procurement blocked capital, leading to ₹176.01 crore in interest losses and ₹114.40 crore in damaged paddy stock. | [CAG MP Audit Report Link](https://cag.gov.in/ag/bihar/en/audit-report/details/28024) [53] |
| **7** | NITI Aayog | 2016 | MSP Evaluation Study: Found that Eastern and North-Eastern states have the lowest access to MSP; proposed Price Deficiency Schemes to limit market price risk. | [NITI Aayog CABI Digital Library](https://www.cabidigitallibrary.org/doi/pdf/10.5555/20203376518) [53] |
| **8** | Food and Agriculture Organization (FAO) / NITI Aayog | 2019 | Joint study of e-NAM in Haryana and Odisha: Confirmed e-NAM reduced cartelization and computerized weighing minimized fraud, but adoption remains low as most trade occurs outside APMC yards. | [FAO Open Knowledge Repository](https://openknowledge.fao.org/bitstreams/152bf7a1-3d43-48d6-b47e-0ccc4a432999/download) [53] |
| **9** | Journal of Agricultural Economics / ResearchGate | 2019 | e-NAM Impacts and Problems: Outlines under-weighment, payment delays, and unauthorized mandi deductions (10-20% of value); slow rollout of assaying facilities limits interstate trade. | [ResearchGate Publication Link](https://www.researchgate.net/publication/330540139_Electronic_National_Agricultural_Markets_Impacts_Problems_and_Way_Forward) [53] |
| **10** | International Journal of Agriculture Extension and Social Development | 2024 | Duggirala e-NAM APMC: Documents trader cartelization (80.83%), lack of live trading displays (89.16%), and delayed same-day payment settlements. | [Extension Journal Repository](https://www.extensionjournal.com/article/view/632/7-5-33) [53] |
| **11** | Department of Food, Civil Supplies & Consumer Protection, GoMP | 2015 | MP e-Uparjan System Overview: Details transition from manual processing to automated SMS queue booking and electronic KYC integration. | [Scribd Document Repository](https://www.scribd.com/document/432450595/E-Uparjan-Computerization-of-Food-Grain-Procurement-System-in-Madhya-Pradesh) [53] |
| **12** | Parliamentary Standing Committee on Agriculture | 2022 | 37th Report on Demands for Grants (2022-2023): Evaluates execution bottlenecks, highlighting regional disparities in procurement infrastructure, fund utilization lags, and state-level coordination deficiencies. | [Lok Sabha eLibrary Repository](https://elibrary.sansad.in/items/a8789409-4623-4e4f-ba83-bd6e5ccff11b) [53] |
| **13** | Asian Journal of Agricultural Extension Economics & Sociology | 2023 | Measures challenges in Rewa, MP, using the Problem Faced Index (PFI); identifies inadequate government digital centers and poor information quality as top barriers. | [ResearchGate Publication Link](https://www.researchgate.net/publication/373952176_Problems_Faced_by_Farmers_Using_Digital_Tools_in_Agriculture_in_Central_Zone_of_India) [53] |
| **14** | Journal of Emerging Technologies and Innovative Research (JETIR) | 2026 | Offline-First Mobile Advisory System: Documents 87% reduction in advisory unavailability, on-device inference averaging 78ms, and synchronization sessions under 100KB using the OpenSync protocol. | [JETIR.org Publication](https://www.jetir.org/papers/JETIR2605145.pdf) [325, 327] |
| **15** | MDPI Mathematics | 2025 | Comprehensive review of truck appointment scheduling models and optimization algorithms (deterministic, stochastic, hybrid) for minimizing port and drayage congestion. | [MDPI Mathematics Publication](https://www.mdpi.com/2227-7390/13/3/503) [260, 268] |

#### 5.2 Missing Links: Highly Targeted Google Search/Scholar Queries
To strengthen this Notebook, download as PDFs and upload the results of these 10 targeted searches:

1.  `site:gov.in filetype:pdf "procurement" AND ("queue management" OR "slot booking" OR "token system")` [243]
2.  `site:mp.gov.in filetype:pdf "e-Uparjan" AND ("RFP" OR "SOP" OR "system architecture")` [243]
3.  `site:gov.in "e-NAM" filetype:pdf AND ("integration challenges" OR "payment delays" OR "technical glitches")` [243]
4.  `site:haryanait.gov.in filetype:pdf "e-Kharid" OR "Meri Fasal Mera Byora" AND ("SOP" OR "technical architecture")` [243]
5.  `site:cag.gov.in "procurement" "paddy" AND ("milling" OR "MSP evasion" OR "audit report")` [243]
6.  `site:cag.gov.in filetype:pdf "Food Corporation of India" AND ("carry over charges" OR "demurrage" OR "transit loss")` [243]
7.  `site:punjab.gov.in filetype:pdf "Anaaj Kharid" AND ("security protocol" OR "MSP payment fraud" OR "token logic")` [243]
8.  `site:telangana.gov.in filetype:pdf "OPMS" OR "paddy procurement" AND ("payment delays" OR "gunny bag shortage")` [243]
9.  `site:sansad.in filetype:pdf "parliamentary question" AND "paddy procurement" AND "payment delays"` [243]
10. `site:gov.in filetype:pdf "PACS computerisation" AND "Bihar" AND "procurement budget limits"` [243]

---
*End of Report.*
