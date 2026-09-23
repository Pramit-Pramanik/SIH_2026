import json
import threading
from typing import Dict, Any, Optional, List, Tuple
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func

from fastapi import HTTPException, status as http_status

from backend.app.models.log import ProcurementLog, WALMutationJournal, VALID_PROCUREMENT_STATES
from backend.app.models.farmer import Farmer
from backend.app.models.mandi import Mandi
from backend.app.models.user import User
from backend.app.core.authorization import assert_transaction_scope
from backend.app.schemas.sync import (
    WALMutationRecord,
    WALBatchSyncRequest,
    WALMutationResult,
    WALBatchSyncResponse,
    SignatureClassification,
)
from backend.app.services.lifecycle_service import validate_lifecycle_transition, STATE_RANK

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
            slot_id = incoming_fields.get("slot_id")
            if slot_id is not None:
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

def reset_sync_state() -> None:
    """Clear in-memory processed mutations registry for test isolation and resets."""
    global _processed_mutations, _current_server_sequence
    with _seq_lock:
        _processed_mutations.clear()
        _current_server_sequence = None

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
    forced_sequence: Optional[int] = None,
    current_user: Optional[User] = None
) -> WALMutationResult:
    """
    Applies a single WAL mutation record idempotently with field-level LWW merge,
    authoritative server sequence assignment, cryptographic/metadata signature classification,
    and persistent WAL journal tracking across process restarts.

    AUD-002 ENFORCEMENT:
    WAL synchronization must NEVER create an authoritative procurement transaction.
    If rec.transaction_id does not already exist in ProcurementLog, REJECT IT with HTTP 404:
    'Cannot synchronize mutation: authoritative transaction does not exist.'
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

    # Fallback to ProcurementLog client_mutation_id check
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

    # 3. Check if ProcurementLog exists (AUD-002: WAL mutations can NEVER create authoritative transactions)
    log = db.query(ProcurementLog).filter(ProcurementLog.transaction_id == rec.transaction_id).first()
    if not log:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Cannot synchronize mutation: authoritative transaction does not exist."
        )

    # 4. Validate foreign keys and tenant matches against the authoritative transaction
    if not rec.farmer_id:
        rec.farmer_id = log.farmer_id
    elif rec.farmer_id != log.farmer_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail=f"Access forbidden: Mutation farmer ID ({rec.farmer_id}) does not match transaction farmer ID ({log.farmer_id})."
        )

    farmer = db.query(Farmer).filter(Farmer.farmer_id == rec.farmer_id).first()
    if not farmer:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Foreign key violation: Farmer {rec.farmer_id} does not exist"
        )

    if not rec.mandi_id:
        rec.mandi_id = log.mandi_id
    elif rec.mandi_id != log.mandi_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail=f"Access forbidden: Mutation mandi ID ({rec.mandi_id}) does not match transaction mandi ID ({log.mandi_id})."
        )

    mandi = db.query(Mandi).filter(Mandi.mandi_id == rec.mandi_id).first()
    if not mandi:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Foreign key violation: Mandi {rec.mandi_id} does not exist"
        )

    # 5. Role scope authorization (AUD-001 tenant boundary enforcement)
    assert_transaction_scope(log, current_user, action_desc="sync WAL mutation")

    # 6. Validate state validity and numerical invariants
    if rec.current_state not in VALID_PROCUREMENT_STATES:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid procurement state: '{rec.current_state}'"
        )

    if "crop_moisture_pct" in incoming_fields and incoming_fields["crop_moisture_pct"] is not None:
        val = float(incoming_fields["crop_moisture_pct"])
        if val < 0 or val > 100:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Moisture percentage {val}% out of valid range [0, 100]"
            )

    for weight_field in ("gross_weight_qt", "tare_weight_qt", "net_weight_qt", "total_payout_inr"):
        if weight_field in incoming_fields and incoming_fields[weight_field] is not None:
            val = float(incoming_fields[weight_field])
            if val < 0:
                raise HTTPException(
                    status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"{weight_field} cannot be negative ({val})"
                )

    gross_val = incoming_fields.get("gross_weight_qt")
    if gross_val is None and log.gross_weight_qt is not None:
        gross_val = float(log.gross_weight_qt)
    tare_val = incoming_fields.get("tare_weight_qt")
    if gross_val is not None and tare_val is not None:
        if float(tare_val) >= float(gross_val):
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Tare weight ({tare_val} qt) cannot be greater than or equal to Gross weight ({gross_val} qt)"
            )

    current_rank = STATE_RANK.get(log.current_state, 0)
    incoming_rank = STATE_RANK.get(rec.current_state, 0)
    is_downstream_already = current_rank > incoming_rank

    # 7. Validate authoritative lifecycle transition from current log state
    # In distributed offline-first sync, if the server is already in a more advanced downstream
    # state (e.g. PAYMENT_SETTLED vs incoming WEIGHED_GROSS), the incoming mutation represents
    # an upstream historical state that has already been incorporated downstream.
    # We do NOT reject with 409 regression; we merge payload attributes and mark CONFLICT_RESOLVED.
    if not is_downstream_already:
        is_valid, err_msg, _ = validate_lifecycle_transition(
            from_state=log.current_state,
            to_state=rec.current_state,
            payload_fields=incoming_fields,
            farmer=farmer,
            db=db,
            current_log=log
        )
        if not is_valid:
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail=f"Lifecycle transition rejected: {err_msg}"
            )

    # 8. Assign authoritative monotonic server receive sequence
    server_seq = forced_sequence if forced_sequence is not None else get_next_server_sequence(db)
    sync_status = "SYNCED"

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
    if is_downstream_already:
        sync_status = "CONFLICT_RESOLVED"
    elif server_seq < existing_seq:
        sync_status = "CONFLICT_RESOLVED"
    elif server_seq == existing_seq and rec.client_mutation_id <= (log.client_mutation_id or ""):
        sync_status = "CONFLICT_RESOLVED"

    # Apply merged fields (preserve authoritative state if transaction is already in a downstream state)
    if not is_downstream_already:
        log.current_state = merged.get("current_state", log.current_state)
    if log.current_state == "ROUTED_TO_WEIGHBRIDGE":
        try:
            from backend.app.services.queue_manager import queue_manager
            queue_manager.remove(log.mandi_id, log.transaction_id)
        except Exception:
            pass

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

    if log.current_state == "WEIGHED_TARE" and log.net_weight_qt is not None:
        try:
            from backend.app.services.eta_service import record_weighbridge_completion
            record_weighbridge_completion(
                db=db,
                mandi_id=log.mandi_id,
                transaction_id=log.transaction_id,
                gross_weight_qt=float(log.gross_weight_qt or 0.0),
                tare_weight_qt=float(log.tare_weight_qt or 0.0),
                net_weight_qt=float(log.net_weight_qt or 0.0),
                scale_id=incoming_fields.get("scale_id") or "SCALE-01",
                completed_at=log.updated_at
            )
        except Exception:
            pass

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
        status=sync_status,
        signature_type=sig_classification,
        created_at=datetime.now(timezone.utc)
    )
    db.merge(journal_entry)

    if sync_status == "SYNCED":
        status_msg = "Mutation successfully synchronized"
    elif is_downstream_already:
        status_msg = f"Mutation state '{rec.current_state}' already incorporated into downstream state '{log.current_state}'"
    else:
        status_msg = "Conflict resolved via LWW ordering"

    return WALMutationResult(
        client_mutation_id=rec.client_mutation_id,
        transaction_id=rec.transaction_id,
        status=sync_status,
        server_receive_sequence=log.server_receive_sequence or server_seq,
        current_state=log.current_state,
        signature_type=sig_classification,
        message=status_msg
    )

def process_wal_batch_sync(
    db: Session,
    request: WALBatchSyncRequest,
    current_user: Optional[User] = None
) -> WALBatchSyncResponse:
    """
    Processes a batch of offline WAL mutations inside a single database transaction.
    Returns per-mutation results with assigned authoritative server sequence.
    Handles per-mutation domain and lifecycle rejections gracefully.
    """
    results: List[WALMutationResult] = []
    synced_count = 0

    for rec in request.mutations:
        result = process_single_wal_mutation(db=db, rec=rec, current_user=current_user)
        results.append(result)
        if result.status in ("SYNCED", "CONFLICT_RESOLVED", "IGNORED_DUPLICATE"):
            synced_count += 1

    db.commit()

    return WALBatchSyncResponse(
        success=all(r.status != "REJECTED" for r in results),
        synced_count=synced_count,
        results=results
    )
