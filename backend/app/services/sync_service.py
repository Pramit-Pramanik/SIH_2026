import json
import threading
from typing import Dict, Any, Optional, List, Tuple
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.models.log import ProcurementLog, WALMutationJournal, VALID_PROCUREMENT_STATES
from backend.app.models.farmer import Farmer
from backend.app.models.mandi import Mandi
from backend.app.schemas.sync import (
    WALMutationRecord,
    WALBatchSyncRequest,
    WALMutationResult,
    WALBatchSyncResponse,
    SignatureClassification,
)
from backend.app.services.lifecycle_service import validate_lifecycle_transition

def classify_signature(
    rec: WALMutationRecord,
    incoming_fields: Dict[str, Any]
) -> str:
    """
    Distinguishes AUTHENTICATED_SIGNATURE from INTEGRITY_METADATA.
    Only describes/classifies as AUTHENTICATED_SIGNATURE if the signature is
    cryptographically verified against server secrets using constant-time comparison.
    Prototype metadata or unverified signatures are classified as INTEGRITY_METADATA.
    """
    sig = rec.hmac_signature
    if not sig or not isinstance(sig, str):
        return SignatureClassification.INTEGRITY_METADATA

    # If 64-character hex string, check against booking signature
    if len(sig) == 64:
        try:
            from backend.app.core.security import verify_booking_signature
            slot_id = incoming_fields.get("slot_id") or 1
            qty = incoming_fields.get("quantity_qt") or incoming_fields.get("net_weight_qt") or 0.0
            if verify_booking_signature(rec.farmer_id, rec.mandi_id, int(slot_id), float(qty), sig):
                return SignatureClassification.AUTHENTICATED_SIGNATURE
        except Exception:
            pass

    return SignatureClassification.INTEGRITY_METADATA

# Thread-safe server receive sequence tracker
_seq_lock = threading.Lock()
_current_server_sequence: Optional[int] = None
_processed_mutations: Dict[str, Tuple[int, str, str]] = {}  # mutation_id -> (server_seq, txn_id, status)

def get_next_server_sequence(db: Session) -> int:
    """
    Atomically increments and returns the next monotonic server_receive_sequence.
    Initializes from the database max(server_receive_sequence) on startup.
    """
    global _current_server_sequence
    with _seq_lock:
        if _current_server_sequence is None:
            max_db = db.query(func.coalesce(func.max(ProcurementLog.server_receive_sequence), 0)).scalar()
            _current_server_sequence = int(max_db) if max_db else 0
        _current_server_sequence += 1
        return _current_server_sequence

def resolve_field_level_lww_merge(
    existing_record: Dict[str, Any],
    incoming_record: Dict[str, Any],
    incoming_mutation_id: str,
    incoming_server_sequence: int,
    incoming_client_timestamp: float
) -> Dict[str, Any]:
    """
    Performs deterministic field-level Last-Write-Wins (LWW) merge on agricultural records.
    Authoritative ordering is determined by server_receive_sequence, NOT client clocks.
    Client timestamp is preserved purely as diagnostic metadata.
    """
    merged = existing_record.copy()
    
    # Track conflict resolution metadata
    if "_conflict_meta" not in merged:
        merged["_conflict_meta"] = {}
        
    for field, new_val in incoming_record.items():
        if field in ("transaction_id", "_conflict_meta", "server_receive_sequence", "client_mutation_id"):
            continue
            
        existing_seq = existing_record.get(f"_seq_{field}", 0)
        existing_mutation_id = existing_record.get(f"_mutation_{field}", "")
        
        # Conflict rule:
        # 1. Higher server receive sequence strictly wins.
        # 2. If same server sequence, deterministic tie-breaker on client_mutation_id.
        should_update = False
        if incoming_server_sequence > existing_seq:
            should_update = True
        elif incoming_server_sequence == existing_seq:
            if incoming_mutation_id > existing_mutation_id:
                should_update = True
                
        if should_update:
            merged[field] = new_val
            merged[f"_seq_{field}"] = incoming_server_sequence
            merged[f"_mutation_{field}"] = incoming_mutation_id
            merged["_conflict_meta"][field] = {
                "authoritative_sequence": incoming_server_sequence,
                "client_mutation_id": incoming_mutation_id,
                "diagnostic_client_ts": incoming_client_timestamp
            }
            
    # Update top-level tracking
    merged["server_receive_sequence"] = max(
        existing_record.get("server_receive_sequence", 0),
        incoming_server_sequence
    )
    merged["client_mutation_id"] = incoming_mutation_id
    
    return merged

def process_single_wal_mutation(
    db: Session,
    rec: WALMutationRecord,
    forced_sequence: Optional[int] = None
) -> WALMutationResult:
    """
    Applies a single WAL mutation record idempotently with field-level LWW merge,
    authoritative server sequence assignment, cryptographic/metadata signature classification,
    and persistent WAL journal tracking across process restarts.
    """
    # 1. Extract incoming payload attributes early to enable validation & signature classification
    incoming_fields: Dict[str, Any] = {"current_state": rec.current_state}
    if rec.payload:
        for k, v in rec.payload.items():
            incoming_fields[k] = v
    elif rec.payload_json:
        try:
            parsed = json.loads(rec.payload_json)
            if isinstance(parsed, dict):
                for k, v in parsed.items():
                    incoming_fields[k] = v
        except json.JSONDecodeError:
            server_seq = forced_sequence if forced_sequence is not None else get_next_server_sequence(db)
            return WALMutationResult(
                client_mutation_id=rec.client_mutation_id,
                transaction_id=rec.transaction_id,
                status="REJECTED",
                server_receive_sequence=server_seq,
                current_state=None,
                signature_type=SignatureClassification.INTEGRITY_METADATA,
                message="Malformed payload_json string"
            )

    # Classify signature: AUTHENTICATED_SIGNATURE vs INTEGRITY_METADATA
    sig_classification = classify_signature(rec, incoming_fields)

    # 2. Idempotent deduplication check.
    # Fast path: in-memory map
    if rec.client_mutation_id in _processed_mutations:
        existing_seq, txn_id, prior_state = _processed_mutations[rec.client_mutation_id]
        return WALMutationResult(
            client_mutation_id=rec.client_mutation_id,
            transaction_id=txn_id,
            status="IGNORED_DUPLICATE",
            server_receive_sequence=existing_seq,
            current_state=prior_state,
            signature_type=sig_classification,
            message="Mutation already processed (idempotent replay)"
        )

    # Persistent WAL journal check (authoritative across process restarts)
    persisted_journal = db.query(WALMutationJournal).filter(
        WALMutationJournal.client_mutation_id == rec.client_mutation_id
    ).first()
    if persisted_journal:
        _processed_mutations[rec.client_mutation_id] = (
            persisted_journal.server_receive_sequence,
            persisted_journal.transaction_id,
            persisted_journal.current_state or ""
        )
        return WALMutationResult(
            client_mutation_id=rec.client_mutation_id,
            transaction_id=persisted_journal.transaction_id,
            status="IGNORED_DUPLICATE",
            server_receive_sequence=persisted_journal.server_receive_sequence,
            current_state=persisted_journal.current_state,
            signature_type=persisted_journal.signature_type,
            message="Mutation already processed by the persisted WAL journal (idempotent replay)"
        )

    # Fallback to ProcurementLog check
    persisted_duplicate = db.query(ProcurementLog).filter(
        ProcurementLog.client_mutation_id == rec.client_mutation_id
    ).first()
    if persisted_duplicate:
        _processed_mutations[rec.client_mutation_id] = (
            persisted_duplicate.server_receive_sequence or 0,
            persisted_duplicate.transaction_id,
            persisted_duplicate.current_state or ""
        )
        return WALMutationResult(
            client_mutation_id=rec.client_mutation_id,
            transaction_id=persisted_duplicate.transaction_id,
            status="IGNORED_DUPLICATE",
            server_receive_sequence=persisted_duplicate.server_receive_sequence or 0,
            current_state=persisted_duplicate.current_state,
            signature_type=sig_classification,
            message="Mutation already processed by the persisted ledger (idempotent replay)"
        )

    # 3. Assign authoritative monotonic server receive sequence
    server_seq = forced_sequence if forced_sequence is not None else get_next_server_sequence(db)

    # 4. Validate foreign keys and basic invariants
    farmer = db.query(Farmer).filter(Farmer.farmer_id == rec.farmer_id).first()
    if not farmer:
        return WALMutationResult(
            client_mutation_id=rec.client_mutation_id,
            transaction_id=rec.transaction_id,
            status="REJECTED",
            server_receive_sequence=server_seq,
            current_state=None,
            signature_type=sig_classification,
            message=f"Foreign key violation: Farmer {rec.farmer_id} does not exist"
        )

    mandi = db.query(Mandi).filter(Mandi.mandi_id == rec.mandi_id).first()
    if not mandi:
        return WALMutationResult(
            client_mutation_id=rec.client_mutation_id,
            transaction_id=rec.transaction_id,
            status="REJECTED",
            server_receive_sequence=server_seq,
            current_state=None,
            signature_type=sig_classification,
            message=f"Foreign key violation: Mandi {rec.mandi_id} does not exist"
        )

    # Validate state validity
    if rec.current_state not in VALID_PROCUREMENT_STATES:
        return WALMutationResult(
            client_mutation_id=rec.client_mutation_id,
            transaction_id=rec.transaction_id,
            status="REJECTED",
            server_receive_sequence=server_seq,
            current_state=None,
            signature_type=sig_classification,
            message=f"Invalid procurement state: '{rec.current_state}'"
        )

    # Invariant validation for numerical fields
    if "crop_moisture_pct" in incoming_fields and incoming_fields["crop_moisture_pct"] is not None:
        val = float(incoming_fields["crop_moisture_pct"])
        if val < 0 or val > 100:
            return WALMutationResult(
                client_mutation_id=rec.client_mutation_id,
                transaction_id=rec.transaction_id,
                status="REJECTED",
                server_receive_sequence=server_seq,
                current_state=rec.current_state,
                signature_type=sig_classification,
                message=f"Moisture percentage {val}% out of valid range [0, 100]"
            )

    for weight_field in ("gross_weight_qt", "tare_weight_qt", "net_weight_qt", "total_payout_inr"):
        if weight_field in incoming_fields and incoming_fields[weight_field] is not None:
            val = float(incoming_fields[weight_field])
            if val < 0:
                return WALMutationResult(
                    client_mutation_id=rec.client_mutation_id,
                    transaction_id=rec.transaction_id,
                    status="REJECTED",
                    server_receive_sequence=server_seq,
                    current_state=rec.current_state,
                    signature_type=sig_classification,
                    message=f"{weight_field} cannot be negative ({val})"
                )

    # 5. Check if ProcurementLog exists
    log = db.query(ProcurementLog).filter(ProcurementLog.transaction_id == rec.transaction_id).first()

    status = "SYNCED"

    if not log:
        # Validate authoritative lifecycle transition for initial creation
        is_valid, err_msg, _ = validate_lifecycle_transition(
            from_state=None,
            to_state=rec.current_state,
            payload_fields=incoming_fields,
            farmer=farmer,
            db=db,
            current_log=None
        )
        if not is_valid:
            return WALMutationResult(
                client_mutation_id=rec.client_mutation_id,
                transaction_id=rec.transaction_id,
                status="REJECTED",
                server_receive_sequence=server_seq,
                current_state=None,
                signature_type=sig_classification,
                message=f"Lifecycle transition rejected: {err_msg}"
            )

        # Initial creation via WAL record
        token_sig = rec.hmac_signature or "OFFLINE_WAL_TOKEN"
        from datetime import date
        from datetime import datetime, timezone

        log = ProcurementLog(
            transaction_id=rec.transaction_id,
            farmer_id=rec.farmer_id,
            mandi_id=rec.mandi_id,
            scheduled_date=date.today(),
            current_state=rec.current_state,
            token_signature=token_sig,
            client_mutation_id=rec.client_mutation_id,
            server_receive_sequence=server_seq,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        # Apply numerical attributes if provided
        if "gross_weight_qt" in incoming_fields and incoming_fields["gross_weight_qt"] is not None:
            log.gross_weight_qt = Decimal(str(incoming_fields["gross_weight_qt"]))
        if "tare_weight_qt" in incoming_fields and incoming_fields["tare_weight_qt"] is not None:
            log.tare_weight_qt = Decimal(str(incoming_fields["tare_weight_qt"]))
        if "net_weight_qt" in incoming_fields and incoming_fields["net_weight_qt"] is not None:
            log.net_weight_qt = Decimal(str(incoming_fields["net_weight_qt"]))
        elif log.gross_weight_qt is not None and log.tare_weight_qt is not None:
            log.net_weight_qt = round(log.gross_weight_qt - log.tare_weight_qt, 2)
        if "crop_moisture_pct" in incoming_fields and incoming_fields["crop_moisture_pct"] is not None:
            log.crop_moisture_pct = Decimal(str(incoming_fields["crop_moisture_pct"]))
        if "total_payout_inr" in incoming_fields and incoming_fields["total_payout_inr"] is not None:
            log.total_payout_inr = Decimal(str(incoming_fields["total_payout_inr"]))

        db.add(log)
    else:
        # Check if already processed on the log directly
        if log.client_mutation_id == rec.client_mutation_id:
            _processed_mutations[rec.client_mutation_id] = (
                log.server_receive_sequence or server_seq,
                log.transaction_id,
                log.current_state
            )
            return WALMutationResult(
                client_mutation_id=rec.client_mutation_id,
                transaction_id=rec.transaction_id,
                status="IGNORED_DUPLICATE",
                server_receive_sequence=log.server_receive_sequence or server_seq,
                current_state=log.current_state,
                signature_type=sig_classification,
                message="Mutation already applied on ledger (idempotent duplicate)"
            )

        # Validate authoritative lifecycle transition from current log state
        is_valid, err_msg, _ = validate_lifecycle_transition(
            from_state=log.current_state,
            to_state=rec.current_state,
            payload_fields=incoming_fields,
            farmer=farmer,
            db=db,
            current_log=log
        )
        if not is_valid:
            return WALMutationResult(
                client_mutation_id=rec.client_mutation_id,
                transaction_id=rec.transaction_id,
                status="REJECTED",
                server_receive_sequence=server_seq,
                current_state=log.current_state,
                signature_type=sig_classification,
                message=f"Lifecycle transition rejected: {err_msg}"
            )

        # Existing record dictionary for LWW merge
        existing_record: Dict[str, Any] = {
            "transaction_id": log.transaction_id,
            "current_state": log.current_state,
            "crop_moisture_pct": float(log.crop_moisture_pct) if log.crop_moisture_pct is not None else None,
            "gross_weight_qt": float(log.gross_weight_qt) if log.gross_weight_qt is not None else None,
            "tare_weight_qt": float(log.tare_weight_qt) if log.tare_weight_qt is not None else None,
            "net_weight_qt": float(log.net_weight_qt) if log.net_weight_qt is not None else None,
            "total_payout_inr": float(log.total_payout_inr) if log.total_payout_inr is not None else None,
            "server_receive_sequence": log.server_receive_sequence or 0,
            "client_mutation_id": log.client_mutation_id or "",
            "_seq_current_state": log.server_receive_sequence or 0,
            "_seq_crop_moisture_pct": log.server_receive_sequence or 0,
            "_seq_gross_weight_qt": log.server_receive_sequence or 0,
            "_seq_tare_weight_qt": log.server_receive_sequence or 0,
            "_seq_net_weight_qt": log.server_receive_sequence or 0,
            "_seq_total_payout_inr": log.server_receive_sequence or 0,
            "_mutation_current_state": log.client_mutation_id or "",
            "_mutation_crop_moisture_pct": log.client_mutation_id or "",
            "_mutation_gross_weight_qt": log.client_mutation_id or "",
            "_mutation_tare_weight_qt": log.client_mutation_id or "",
            "_mutation_net_weight_qt": log.client_mutation_id or "",
            "_mutation_total_payout_inr": log.client_mutation_id or "",
        }

        # Resolve field-level LWW merge
        merged = resolve_field_level_lww_merge(
            existing_record=existing_record,
            incoming_record=incoming_fields,
            incoming_mutation_id=rec.client_mutation_id,
            incoming_server_sequence=server_seq,
            incoming_client_timestamp=rec.client_timestamp
        )

        # Detect if any conflict arose (i.e. incoming was older than existing or partially overwritten)
        existing_seq = log.server_receive_sequence or 0
        if server_seq < existing_seq:
            status = "CONFLICT_RESOLVED"
        elif server_seq == existing_seq and rec.client_mutation_id <= (log.client_mutation_id or ""):
            status = "CONFLICT_RESOLVED"

        # Apply merged fields
        log.current_state = merged.get("current_state", log.current_state)
        if merged.get("gross_weight_qt") is not None:
            log.gross_weight_qt = Decimal(str(merged["gross_weight_qt"]))
        if merged.get("tare_weight_qt") is not None:
            log.tare_weight_qt = Decimal(str(merged["tare_weight_qt"]))
        if merged.get("net_weight_qt") is not None:
            log.net_weight_qt = Decimal(str(merged["net_weight_qt"]))
        elif log.gross_weight_qt is not None and log.tare_weight_qt is not None:
            log.net_weight_qt = round(log.gross_weight_qt - log.tare_weight_qt, 2)
        if merged.get("crop_moisture_pct") is not None:
            log.crop_moisture_pct = Decimal(str(merged["crop_moisture_pct"]))
        if merged.get("total_payout_inr") is not None:
            log.total_payout_inr = Decimal(str(merged["total_payout_inr"]))

        log.server_receive_sequence = merged.get("server_receive_sequence", server_seq)
        log.client_mutation_id = merged.get("client_mutation_id", rec.client_mutation_id)
        from datetime import datetime, timezone
        log.updated_at = datetime.now(timezone.utc)

    db.flush()

    # Track in processed mutations registry (in-memory fast-path)
    _processed_mutations[rec.client_mutation_id] = (
        log.server_receive_sequence or server_seq,
        log.transaction_id,
        log.current_state
    )

    # Persist in WALMutationJournal for restart idempotency
    from datetime import datetime, timezone
    journal_entry = WALMutationJournal(
        client_mutation_id=rec.client_mutation_id,
        transaction_id=rec.transaction_id,
        server_receive_sequence=log.server_receive_sequence or server_seq,
        current_state=log.current_state,
        status=status,
        signature_type=sig_classification,
        created_at=datetime.now(timezone.utc)
    )
    db.merge(journal_entry)

    return WALMutationResult(
        client_mutation_id=rec.client_mutation_id,
        transaction_id=rec.transaction_id,
        status=status,
        server_receive_sequence=log.server_receive_sequence or server_seq,
        current_state=log.current_state,
        signature_type=sig_classification,
        message="Mutation successfully synchronized" if status == "SYNCED" else "Conflict resolved via LWW ordering"
    )

def process_wal_batch_sync(
    db: Session,
    request: WALBatchSyncRequest
) -> WALBatchSyncResponse:
    """
    Processes a batch of offline WAL mutations inside a single database transaction.
    Returns per-mutation results with assigned authoritative server sequence.
    """
    results: List[WALMutationResult] = []
    synced_count = 0

    for rec in request.mutations:
        result = process_single_wal_mutation(db=db, rec=rec)
        results.append(result)
        if result.status in ("SYNCED", "CONFLICT_RESOLVED", "IGNORED_DUPLICATE"):
            synced_count += 1

    db.commit()

    return WALBatchSyncResponse(
        success=all(r.status != "REJECTED" for r in results),
        synced_count=synced_count,
        results=results
    )
