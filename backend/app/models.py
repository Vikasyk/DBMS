from datetime import date
from decimal import Decimal
from typing import Annotated, Literal, Optional

from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field


BatchId = Annotated[str, Field(pattern=r"^B[0-9]+$", max_length=12)]
FarmId = Annotated[str, Field(pattern=r"^F[0-9]+$", max_length=10)]
FacilityId = Annotated[str, Field(pattern=r"^PF[0-9]+$", max_length=10)]
RetailerId = Annotated[str, Field(pattern=r"^R[0-9]+$", max_length=10)]
Quantity = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=3)]
Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
PhoneNumber = Annotated[str, Field(pattern=r"^\+?[0-9]{10,14}$")]
Unit = Literal["kg", "L", "unit"]
BatchStatus = Literal["ACTIVE", "ON_HOLD", "RECALLED", "CLOSED"]
CheckStage = Literal["FARM", "PROCESSING", "DISTRIBUTION", "RETAIL"]
CheckResult = Literal["PASS", "FAIL", "INCONCLUSIVE"]
Operation = Literal["CLEANING", "SORTING", "PULPING", "MIXING", "PACKAGING", "COLD_STORAGE", "OTHER"]
PriceStage = Literal["FARM", "PROCESSING_WHOLESALE", "RETAIL"]
AlertStatus = Literal["OPEN", "REVIEWED", "DISMISSED"]
PageSize = Annotated[int, Query(ge=1, le=200)]
PageOffset = Annotated[int, Query(ge=0)]


class RequestBody(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class Address(RequestBody):
    street: Optional[str] = Field(default=None, min_length=1, max_length=150)
    city: str = Field(min_length=1, max_length=60)
    state: str = Field(min_length=1, max_length=60)
    pin_code: str = Field(pattern=r"^[1-9][0-9]{5}$")


class FarmCreate(Address):
    farm_name: str = Field(min_length=1, max_length=100)
    contact_numbers: list[PhoneNumber] = Field(default_factory=list, max_length=20)


class FacilityCreate(Address):
    facility_name: str = Field(min_length=1, max_length=100)


class RetailerCreate(Address):
    retailer_name: str = Field(min_length=1, max_length=100)
    contact_numbers: list[PhoneNumber] = Field(default_factory=list, max_length=20)


class BatchFields(RequestBody):
    product_name: str = Field(min_length=1, max_length=60)
    quantity: Quantity
    unit: Unit
    production_date: date
    expiry_date: date


class BatchCreate(BatchFields):
    farm_id: FarmId


class BatchStatusUpdate(RequestBody):
    status: BatchStatus


class ProcessingInput(RequestBody):
    batch_id: BatchId
    quantity_used: Quantity


class ProcessingCreate(BatchFields):
    facility_id: FacilityId
    operation_type: Operation
    inputs: list[ProcessingInput] = Field(min_length=1)
    allow_over_allocation: bool = False


class HandlingCreate(RequestBody):
    facility_id: FacilityId
    processing_date: date
    operation_type: Operation


class QualityCheckCreate(RequestBody):
    batch_id: BatchId
    check_date: date
    check_stage: CheckStage
    result: CheckResult
    contamination_type: Optional[str] = Field(default=None, min_length=1, max_length=40)
    remarks: Optional[str] = None


class SimulationRequest(RequestBody):
    batch_id: BatchId


class ShipmentItem(RequestBody):
    batch_id: BatchId
    quantity_shipped: Quantity


class ShipmentCreate(RequestBody):
    shipment_date: date
    source_location: str = Field(min_length=1, max_length=150)
    retailer_id: RetailerId
    transportation_cost: Money
    items: list[ShipmentItem] = Field(min_length=1)


class PriceCreate(RequestBody):
    batch_id: BatchId
    price_date: date
    supply_chain_stage: PriceStage
    selling_price: Money
    cost_per_unit: Optional[Money] = None
    market_location: str = Field(min_length=1, max_length=60)


class RuleRun(RequestBody):
    tolerance: Decimal = Field(default=Decimal("0.02"), ge=0)


class AlertStatusUpdate(RequestBody):
    alert_status: Literal["REVIEWED", "DISMISSED"]


class NaturalLanguageQuestion(RequestBody):
    question: str = Field(min_length=1, max_length=500)
