# Domain Integrity Rules

1. **Single State Active**: A procurement lot transaction ID must belong to exactly one state in the lifecycle state machine at any given time:
   `SLOT_BOOKED`, `GATE_ENTRY_VERIFIED`, `IN_QA_QUEUE`, `QUALITY_APPROVED`, `ROUTED_TO_WEIGHBRIDGE`, `WEIGHED_GROSS`, `WEIGHED_TARE`, `BILL_GENERATED`, `DBT_PAYMENT_INITIATED`, `PAYMENT_SETTLED` (or terminal `QUALITY_REJECTED` / retryable `PAYMENT_FAILED`).
2. **State Reversion Prohibition**: Transactions cannot move backward in the state machine except from `PAYMENT_FAILED` back to `DBT_PAYMENT_INITIATED` for retry.
3. **Quality Separation from Queue Priority**: 
   - DCDQ determines queue ordering for eligible arrived lots.
   - Quality assaying rules determine whether a crop lot is eligible for procurement.
   - Crop lots with moisture $>17.0\%$ MUST immediately trigger transition to `QUALITY_REJECTED` and route to the drying apron, completely overriding queue priority. A rejected lot cannot appear in the weighbridge queue unless authenticated with a supervisor override token. Never allow a high DCDQ score to bypass a quality rejection.
4. **Authoritative Yield Ceiling & Atomic Locking**: Total quantity sold across all bookings and weighments must never exceed `production_ceiling_qt` ($\sum Q_{\text{delivered}} \le \text{production\_ceiling\_qt}$). The `production_ceiling_qt` stored on the verified farmer profile is authoritative. Yield ceiling validation and quantity reservation must occur atomically inside the same transaction/locking boundary.
5. **Dual-Signature Payout Authorization**: Transition to `DBT_PAYMENT_INITIATED` requires valid, independent HMAC-SHA256 signatures from both the Procurement Inspector and Mandi Operator. Single-signature approvals are strictly rejected.
