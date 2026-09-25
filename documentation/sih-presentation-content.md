# SIH 2026 Presentation Text: MandiQ Platform
**Drafted by:** SIH Technical Architect & Agri-Tech Strategist
**Date:** September 08, 2026

---

### Slide 1: TITLE PAGE

*   **Problem Statement ID:** SIH1578
*   **Problem Statement Title:** Smart Queue Management, Offline Transaction Syncing, and Secure DBT Authorization for State Agricultural Procurement Portals
*   **Theme:** Smart Automation / AgriTech / E-Governance
*   **PS Category:** Software
*   **Team ID:** SIH2026-TEAM-MANDIQ
*   **Team Name:** Code-Krishi Architects

---

### Slide 2: IDEA TITLE

*   **Proposed Solution:**
    *   **MandiQ** is a decentralized, offline-resilient, dynamic queue management and tamper-proof payment authorization platform for agricultural procurement yards (mandis) [17, 44].
*   **Detailed Explanation:**
    *   **Dynamic Multi-Criteria Priority Queue:** Replaces rigid First-Come, First-Served (FCFS) check-ins with an algorithm-driven Virtual Queue that continuously recalculates priority scores ($S_i$) based on crop moisture, transit delay, and wait-time [17, 44].
    *   **Offline-First Transaction Syncing:** Implements an edge-computing architecture using local IndexedDB write-ahead logging to process gate entries, weighments, and grading during complete network blackouts [44].
    *   **Zero-Data Interactive Portal:** Provides a signaling-layer USSD portal, enabling low-income and feature-phone farmers to book slots, check prices, and monitor queue lines without internet [44].
    *   **Cryptographic DBT Authorization:** Employs multi-signature approval and immutable verification hashes for modifying bank coordinates, completely neutralizing procurement portal fraud [44].
*   **How It Addresses the Problem:**
    *   Eliminates high latency and database timeouts during harvest spikes by localizing transactions at the mandi edge [44].
    *   Prevents direct benefit transfer (DBT) payment redirection and land database manipulation by enforcing zero-trust cryptographic ledger integrity [44].
*   **Innovation and Uniqueness:**
    *   **Continuous Capacity Calibration:** Recalculates slots dynamically using physical weighbridge throughput rather than paper-based quotas [44].
    *   **Perishability-Aware Scheduling:** Automatically prioritizes high-moisture crops to prevent post-harvest spoilage in open-air yards [44].
    *   **Hardware-to-Software Bridge:** Direct, tamper-proof IoT scale integrations that bypass manual entry fields entirely [44].

---

### Slide 3: TECHNICAL APPROACH

*   **Technologies to be Used:**
    *   **Frontend:** Progressive Web App (Vite + React 18 PWA), 5 Dedicated Role Portals, Tailwind CSS, IndexedDB (Dexie.js WAL) [17, 44].
    *   **Backend:** Python 3.11+ (FastAPI) async modular monolith with native BackgroundTasks, Redis 7.2 for in-memory queue states & distributed locking [17, 44].
    *   **In-Memory Cache:** Redis Sorted Sets (ZSET) for tracking real-time queue states and instant ETA updates [17, 44].
    *   **Database:** PostgreSQL (Primary Relational Ledger with ACID compliance) [17, 44].
    *   **Gateways:** USSD Gateway (MAP-layer signaling), Twilio/Gupshup SMS API, NPCI/PFMS mock gateways [17, 44].
*   **Methodology and Process for Implementation:**
    *   **Step 1: Offline Edge Onboarding:** Farmer checks in via PWA QR code or USSD; local edge node validates registration and generates a secure HMAC token [44].
    *   **Step 2: Real-Time Priority Scoring:** Moisture sensors input crop data via API; the backend calculates $S_i$ and pushes the token to a Redis Sorted Set [17, 44].
    *   **Step 3: Automated Weighment Integration:** Bluetooth digital scales broadcast data to the edge DB, generating an immutable transaction J-Form receipt [17, 44].
    *   **Step 4: Gzip-Asynchronous Sync:** When internet recovers, local sync workers compress transaction packets (30KB) and update the state central database [44].
    *   **Step 5: Multi-Sig DBT Settlement:** Invoices are cryptographically signed by the inspector and operator before trigger-firing direct bank payouts [17, 44].
*   **Visual Diagram Recommendation:**
    *   *Place a 3-tier architecture flowchart here:* Illustrating (1) Client Edge/USSD Touchpoints, (2) Local Mandi Node containing SQLite/Redis operating completely offline, and (3) The Central E-Governance Cloud synced via compressed binary packets when back online.

---

### Slide 4: FEASIBILITY AND VIABILITY

*   **Analysis of Feasibility:**
    *   **Technical Feasibility:** Highly viable. Caching in IndexedDB, light Redis queue processing, and USSD messaging require minimal compute and run on existing basic mandi PCs [17, 44].
    *   **Financial Viability:** High ROI. Avoids multimillion-dollar cloud infrastructure scaling, significantly reduces open storage (CAP) grain spoilage, and stops multi-crore payment fraud [44, 68].
*   **Potential Challenges and Risks:**
    *   **Risk 1: Split-Brain Sync Conflicts:** Intermittent internet causing concurrent or duplicate state changes at local nodes versus central servers [44].
    *   **Risk 2: Hardware Wear and Tear:** Dirt, dust, and moisture in harsh mandi environments causing IoT weighment or moisture sensor failure [44].
    *   **Risk 3: User Adoption and Operational Inertia:** Resistance from commission agents (arhtiyas) and low-literacy farmers [44, 50].
*   **Strategies for Overcoming These Challenges:**
    *   **Vector Timestamps:** Implement deterministic field-level logical clocks to resolve database merge conflicts seamlessly [44].
    *   **Dual-Override Operator Flow:** Allow manual scale inputs only with a secondary physical supervisor key, logging all overrides for audit [44].
    *   **USSD-Guided Voice Prompts:** Provide automated interactive voice response (IVR) and USSD menu navigation in regional languages [44].

---

### Slide 5: IMPACT AND BENEFITS

*   **Potential Impact on the Target Audience:**
    *   **Smallholder & Tenant Farmers:** Eliminates 3–4 hour long wait-times, protects against biometric POS failures, and secures bank accounts from fraud [44, 72].
    *   **Mandi Operators:** Eradicates manual ledger reconciliation errors and server crash bottlenecks [44].
    *   **State Civil Supplies Departments:** Full audit trails of every procurement grain lot, from gate pass to direct payment [44].
*   **Benefits of the Solution:**
    *   **Economic:** Prevents transport fuel waste, eliminates unscientific open CAP damage, and stops payment diversion scams [44, 68].
    *   **Technical:** 100% operational uptime through localized edge-computing nodes; seamless asynchronous backend coordination [44].
    *   **Social:** Financial inclusion of smallholders and informal tenant farmers who lack smartphones or formal internet [44].

---

### Slide 6: RESEARCH AND REFERENCES

*   **Details & Strategic Foundations:**
    *   **CAG Audit Reports:** Performance Audit Report No. 20 of 2023 highlights massive grain damage in open storage due to delayed yard lifting and weak transport coordinating [68].
    *   **Mandi Cyber-Fraud Analysis:** Based on actual Punjab Police findings regarding the 2024 Anaaj Kharid portal scam where operator logins were hacked to redirect DBT funds to synthetic accounts [51].
    *   **Mathematical Logistics Foundations:** Uses Little's Law and non-stationary queuing theory ($M(t)/E_k/c(t)$) to model dynamic vehicle scheduling and truck dock throughput [63, 66].
    *   **Digital Exclusion Studies:** Research in Haryana and MP confirms that mandatory biometrics and registration mismatch errors lock out up to 60% of smallholder farmers [72, 75].
