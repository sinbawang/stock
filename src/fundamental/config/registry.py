"""Registry lookups for fundamental submodels."""

from typing import Dict, Optional

from .finance_submodels import BANK_V1, BROKER_V1, INSURANCE_V1
from .models import SubmodelConfig
from .tech_submodels import (
    GAME_CONTENT_V1,
    INDUSTRIAL_AUTOMATION_V1,
    PLATFORM_INTERNET_V1,
    SEMICONDUCTOR_HARDTECH_V1,
)

SUBMODEL_REGISTRY: Dict[str, SubmodelConfig] = {
    BANK_V1.submodel_id: BANK_V1,
    INSURANCE_V1.submodel_id: INSURANCE_V1,
    BROKER_V1.submodel_id: BROKER_V1,
    PLATFORM_INTERNET_V1.submodel_id: PLATFORM_INTERNET_V1,
    SEMICONDUCTOR_HARDTECH_V1.submodel_id: SEMICONDUCTOR_HARDTECH_V1,
    INDUSTRIAL_AUTOMATION_V1.submodel_id: INDUSTRIAL_AUTOMATION_V1,
    GAME_CONTENT_V1.submodel_id: GAME_CONTENT_V1,
}

SYMBOL_TO_SUBMODEL: Dict[str, str] = {}
for _config in SUBMODEL_REGISTRY.values():
    for _symbol in _config.applicable_symbols:
        SYMBOL_TO_SUBMODEL[_symbol] = _config.submodel_id


def get_submodel(submodel_id: str) -> SubmodelConfig:
    return SUBMODEL_REGISTRY[submodel_id]


def get_submodel_for_symbol(symbol: str) -> Optional[SubmodelConfig]:
    submodel_id = SYMBOL_TO_SUBMODEL.get(symbol)
    if submodel_id is None:
        return None
    return SUBMODEL_REGISTRY[submodel_id]
