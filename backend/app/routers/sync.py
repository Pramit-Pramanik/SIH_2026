import gzip
import json
from typing import Optional, Union, Dict, Any
from fastapi import APIRouter, Depends, Request, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.dependencies.get_db import get_db
from backend.app.dependencies.auth import require_roles
from backend.app.models.user import User
from backend.app.models.log import ProcurementLog
from backend.app.schemas.sync import (
    WALMutationRecord,
    WALBatchSyncRequest,
    WALBatchSyncResponse,
)
from backend.app.services.sync_service import (
    process_wal_batch_sync,
    get_next_server_sequence,
    _current_server_sequence,
)

router = APIRouter(prefix="/sync", tags=["Offline WAL Synchronization"])

@router.post(
    "/wal",
    response_model=WALBatchSyncResponse,
    summary="Synchronize offline WAL mutation batch (supports raw JSON or Gzip compressed payload)",
    status_code=status.HTTP_200_OK
)
async def sync_offline_wal(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(require_roles(["OPERATOR", "SUPERVISOR", "ADMIN"]))
) -> WALBatchSyncResponse:
    """
    Ingests and synchronizes offline WAL mutations recorded by client devices during network blackouts.
    Supports Gzip-compressed bodies (Content-Encoding: gzip or gzip magic bytes) to ensure
    payloads stay under 100 KB per 50 records as specified in AC-008.
    
    Assigns authoritative server_receive_sequence and resolves conflicts via field-level LWW merge.
    """
    body_bytes = await request.body()
    content_encoding = request.headers.get("content-encoding", "").lower()
    content_type = request.headers.get("content-type", "").lower()

    # Check if payload is Gzip compressed
    is_gzip = "gzip" in content_encoding or body_bytes.startswith(b"\x1f\x8b")

    if is_gzip:
        try:
            decompressed = gzip.decompress(body_bytes)
            raw_json = json.loads(decompressed.decode("utf-8"))
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to decompress or parse Gzip payload: {exc}"
            )
    else:
        try:
            raw_json = json.loads(body_bytes.decode("utf-8"))
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid JSON body: {exc}"
            )

    # Normalize single mutation vs batch mutation
    if isinstance(raw_json, list):
        batch_dict = {"mutations": raw_json}
    elif isinstance(raw_json, dict):
        if "mutations" in raw_json:
            batch_dict = raw_json
        else:
            # Single mutation payload
            batch_dict = {"mutations": [raw_json]}
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Payload must be a JSON object with 'mutations' or an array of mutations"
        )

    try:
        sync_req = WALBatchSyncRequest(**batch_dict)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Schema validation error: {exc}"
        )

    response = process_wal_batch_sync(db=db, request=sync_req)
    return response

@router.get(
    "/status",
    summary="Get current server synchronization status and sequence watermark",
    status_code=status.HTTP_200_OK
)
def get_sync_status(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Returns current authoritative server sequence number and sync ledger statistics.
    """
    max_seq = db.query(func.coalesce(func.max(ProcurementLog.server_receive_sequence), 0)).scalar()
    total_logs = db.query(func.count(ProcurementLog.transaction_id)).scalar()

    return {
        "status": "operational",
        "authoritative_sequence_watermark": int(max_seq) if max_seq else 0,
        "total_ledger_transactions": total_logs or 0
    }
