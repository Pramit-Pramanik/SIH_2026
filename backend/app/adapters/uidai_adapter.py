from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from backend.app.models.farmer import Farmer

class UidaiMockAdapter:
    """
    Mock adapter simulating external UIDAI e-KYC and state land registry systems (AgriStack).
    Provides verified farmer profile, land acreage, and crop yield ceilings.
    """
    is_mock: bool = True
    adapter_name: str = "UIDAI-AGRISTACK-MOCK-GATEWAY"

    @classmethod
    def verify_aadhaar_and_fetch_land_record(
        cls,
        db: Session,
        aadhaar_hash: str
    ) -> Optional[Dict[str, Any]]:
        """
        Looks up registered farmer profile in the ledger to simulate state land registry verification.
        Returns verified land record dictionary or None if not found.
        """
        farmer = db.query(Farmer).filter(Farmer.aadhaar_hash == aadhaar_hash).first()
        if not farmer:
            return None

        return {
            "is_mock": cls.is_mock,
            "adapter": cls.adapter_name,
            "farmer_id": farmer.farmer_id,
            "aadhaar_hash": farmer.aadhaar_hash,
            "farmer_name": farmer.name,
            "mobile_number": farmer.mobile_number,
            "registered_crop_type": farmer.registered_crop_type,
            "land_area_hectares": float(farmer.land_area_hectares),
            "production_ceiling_qt": float(farmer.production_ceiling_qt),
            "khata_number": f"KH-{farmer.farmer_id:04d}",
            "verification_status": "VERIFIED_UIDAI_AGRISTACK"
        }
