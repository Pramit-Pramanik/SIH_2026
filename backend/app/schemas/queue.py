from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class QueueItem(BaseModel):
    """
    Representation of a single vehicle ranked in the active mandi priority queue.
    """
    model_config = ConfigDict(extra="forbid")

    rank: int = Field(..., description="1-indexed position in active queue (1 = highest priority)")
    transaction_id: str
    priority_score: float = Field(..., description="DCDQ composite priority score (S_i)")
    arrival_timestamp: Optional[float] = None
    farmer_id: Optional[int] = None
    quantity_qt: Optional[float] = None


class QueueListResponse(BaseModel):
    """
    Active vehicle queue list ordered by descending priority score.
    """
    model_config = ConfigDict(extra="forbid")

    mandi_id: int
    total_vehicles: int
    items: List[QueueItem]


class QueueDispatchResponse(BaseModel):
    """
    Response schema when the top vehicle is popped/dispatched to the weighbridge.
    """
    model_config = ConfigDict(extra="forbid")

    mandi_id: int
    transaction_id: str
    priority_score: float
    new_state: str = Field(default="ROUTED_TO_WEIGHBRIDGE")
    dispatched_at: str
    message: str


class QueueStatusResponse(BaseModel):
    """
    Response schema for checking a specific vehicle's rank and priority in the queue.
    """
    model_config = ConfigDict(extra="forbid")

    mandi_id: int
    transaction_id: str
    in_queue: bool
    priority_score: Optional[float] = None
    rank: Optional[int] = None
    total_ahead: Optional[int] = None
