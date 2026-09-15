from typing import Dict, Any, List, Optional
from decimal import Decimal

# Simulated AGMARKNET Portal / Directorate of Economics & Statistics MSP Rates
OFFICIAL_MSP_RATES_INR_PER_QT: Dict[str, Decimal] = {
    "Wheat": Decimal("2275.00"),
    "Paddy": Decimal("2183.00"),
    "Paddy (Common)": Decimal("2183.00"),
    "Mustard": Decimal("5650.00"),
    "Gram": Decimal("5440.00"),
    "Bajra": Decimal("2500.00"),
    "Maize": Decimal("2090.00"),
}

class AgmarknetMockAdapter:
    """
    Mock adapter simulating AGMARKNET agricultural marketing price portal.
    Provides deterministic Minimum Support Prices (MSP) for zero-data USSD and billing lookups.
    """
    is_mock: bool = True
    adapter_name: str = "AGMARKNET-PRICE-FEED-SIMULATOR"

    @classmethod
    def get_current_msp_rates(cls) -> Dict[str, Any]:
        """
        Returns all active MSP rates with mock service metadata.
        """
        return {
            "is_mock": cls.is_mock,
            "adapter": cls.adapter_name,
            "marketing_season": "Rabi/Kharif 2025-26",
            "rates_inr_per_qt": {
                crop: float(price)
                for crop, price in OFFICIAL_MSP_RATES_INR_PER_QT.items()
            }
        }

    @classmethod
    def get_crop_msp(cls, crop_type: str) -> Optional[float]:
        """
        Returns the official MSP rate for a specific crop name, or None if not found.
        """
        normalized = crop_type.strip()
        for key, price in OFFICIAL_MSP_RATES_INR_PER_QT.items():
            if key.lower() == normalized.lower():
                return float(price)
        return None
