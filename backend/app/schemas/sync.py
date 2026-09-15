from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict

class WALMutationRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    client_mutation_id: str = Field(..., description="Deterministic client mutation UUID for identity and deduplication")
    transaction_id: str = Field(..., description="Domain transaction UUID")
    farmer_id: int = Field(..., description="Farmer ID")
    mandi_id: int = Field(..., description="Mandi ID")
    current_state: str = Field(..., description="Lifecycle state for this mutation")
    payload: Optional[Dict[str, Any]] = Field(default=None, description="Structured mutation payload")
    payload_json: Optional[str] = Field(default=None, description="Stringified payload attributes")
    hmac_signature: Optional[str] = Field(default=None, description="Cryptographic signature from client/token")
    client_timestamp: float = Field(..., description="Local epoch milliseconds or seconds (diagnostic metadata only)")
    mutation_type: Optional[str] = Field(default=None, description="Type of mutation e.g. GATE_CHECK_IN, GROSS_WEIGHMENT")

class WALBatchSyncRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    mutations: List[WALMutationRecord] = Field(default_factory=list, description="List of pending mutations to synchronize")

class WALMutationResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    client_mutation_id: str
    transaction_id: str
    status: str = Field(..., description="SYNCED, CONFLICT_RESOLVED, IGNORED_DUPLICATE, or REJECTED")
    server_receive_sequence: int = Field(..., description="Authoritative server sequence assigned to this mutation")
    current_state: Optional[str] = None
    message: Optional[str] = None

class WALBatchSyncResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    success: bool
    synced_count: int
    results: List[WALMutationResult]
