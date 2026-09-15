# System Domain Dictionary

| Term | Domain | Definition | Technical Representation |
| :--- | :--- | :--- | :--- |
| `mandi_id` | Master Infrastructure | Unique identifier for an APMC procurement yard. | `INTEGER PRIMARY KEY` |
| `aadhaar_hash` | Identity | SHA-256 anonymized hash of farmer's Aadhaar UID. | `VARCHAR(64) UNIQUE NOT NULL` |
| `production_ceiling_qt` | Agriculture | Maximum allowable sales volume for a farmer based on verified acreage. | `NUMERIC(10, 2) NOT NULL` |
| `priority_score` | Scheduling | Computed DCDQ score ($S_i$) used to rank vehicles in the queue. | `NUMERIC(8, 4)` |
| `hmac_signature` | Security | SHA-256 HMAC signature authorizing offline token validity. | `VARCHAR(64) NOT NULL` |
