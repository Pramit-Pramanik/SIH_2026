from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class LockTimelineEvent(BaseModel):
    worker_id: int
    request_id: str
    acquired_at_ms: float
    released_at_ms: float
    duration_ms: float
    status: str
    token: str


class ConcurrentBookingTestRequest(BaseModel):
    mandi_id: int = Field(description="Target APMC mandi ID for slot booking")
    slot_id: Optional[int] = Field(default=None, description="Optional target slot ID; auto-selected if None")
    concurrent_requests: int = Field(default=10, ge=2, le=50, description="Number of concurrent reservation attempts")
    request_qty_qt: float = Field(default=10.0, gt=0, description="Requested produce quantity in quintals")


class ConcurrentBookingTestResponse(BaseModel):
    mandi_id: int
    slot_id: int
    total_requests: int
    successful_requests: int
    rejected_requests: int
    capacity_exceeded: int = Field(default=0, description="Zero tolerance invariant: strictly 0")
    allocated_capacity_qt: float
    booked_capacity_qt: float
    remaining_capacity_qt: float
    lock_mechanism: str = "Redis SET NX PX Distributed Mutex (Prototype)"
    timeline: List[LockTimelineEvent]
    summary: str


class LWWFieldComparison(BaseModel):
    field: str
    old_value: Any
    incoming_value: Any
    winner: Any
    winning_mutation_id: str
    authoritative_sequence: int
    reason: str
    client_timestamp_a: str
    client_timestamp_b: str


class LWWConflictTestRequest(BaseModel):
    mutation_a: Optional[Dict[str, Any]] = None
    mutation_b: Optional[Dict[str, Any]] = None


class LWWConflictTestResponse(BaseModel):
    transaction_id: str
    mutation_a_id: str
    mutation_a_sequence: int
    mutation_b_id: str
    mutation_b_sequence: int
    fields: List[LWWFieldComparison]
    governance_model: str = "Authoritative Server Sequence (server_receive_sequence)"
    governance_notice: str = (
        "Governance Rule: Authoritative conflict ordering is governed by server_receive_sequence, "
        "not client clocks. Client timestamps are retained solely as diagnostic metadata."
    )


class GzipSyncEvidenceRequest(BaseModel):
    record_count: Optional[int] = Field(default=10, ge=1, le=100, description="Number of WAL records in batch")


class GzipSyncEvidenceResponse(BaseModel):
    record_count: int
    raw_size_bytes: int
    compressed_size_bytes: int
    compression_ratio_pct: float
    decompression_status: str
    verified: bool
    pipeline: str = "IndexedDB WAL -> Batch (Raw) -> Gzip Compress -> HTTP POST -> Decompress -> DB Sync"


class HMACVerificationRequest(BaseModel):
    farmer_id: int = Field(description="Registered farmer ID")
    mandi_id: int = Field(description="Target APMC mandi ID")
    slot_id: int = Field(default=5, description="Procurement slot ID")
    quantity_qt: float = Field(default=25.0, gt=0, description="Reserved produce quantity in quintals")
    tamper_quantity_qt: Optional[float] = Field(default=250.0, description="Tampered produce quantity to test rejection")


class HMACVerificationResponse(BaseModel):
    canonical_payload: str
    signature_length_chars: int = 64
    signature_preview: str
    secret_key_status: str = "PROTECTED (256-bit cryptographic entropy; strictly unexposed in frontend/API)"
    verification_result: str
    is_valid: bool
    tampered_payload: str
    tampered_result: str
    tamper_rejected: bool
    algorithm: str = "HMAC-SHA256 (FIPS 198-1)"
    execution_trace: List[str]
    verification_status: str = "VERIFIED_CRYPTO_INTEGRITY"


class DCDQVehicleDemoItem(BaseModel):
    transaction_id: str
    farmer_name: str
    crop_type: str
    payload_qt: float
    moisture_pct: float
    wait_minutes: float
    planned_arrival_offset_min: float
    actual_arrival_offset_min: float
    score_a: float = Field(description="Appointment Adherence (A_i)")
    score_d: float = Field(description="Demurrage & Weight (D_i)")
    score_m: float = Field(description="Moisture Risk Index (M_i)")
    score_w: float = Field(description="Anti-Starvation Wait Bonus (W_i)")
    composite_score_s: float = Field(description="Composite Priority Score (S_i)")
    rank: int


class DCDQReorderDemoRequest(BaseModel):
    mandi_id: int = Field(description="Target APMC mandi ID")
    tweak_transaction_id: Optional[str] = Field(default=None, description="Transaction to tweak")
    delta_wait_minutes: Optional[float] = Field(default=45.0, description="Additional wait time to add")
    new_moisture_pct: Optional[float] = Field(default=None, description="New moisture percentage")


class DCDQReorderDemoResponse(BaseModel):
    mandi_id: int
    tweak_target: str
    before_queue: List[DCDQVehicleDemoItem]
    after_queue: List[DCDQVehicleDemoItem]
    rank_changed: bool
    previous_rank: int
    new_rank: int
    reorder_explanation: str
    execution_trace: List[str]
    verification_status: str = "VERIFIED_DYNAMIC_REORDER"


class AlgorithmShowcaseResetResponse(BaseModel):
    status: str = "SUCCESS"
    demo_records_purged: int
    demo_slots_reset: int
    scale_overrides_cleared: bool
    operational_data_protected: bool = True
    new_demo_run_id: str
    message: str

