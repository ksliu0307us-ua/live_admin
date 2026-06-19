from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, EmailStr, Field


# --- Auth schemas ---

class RegisterRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=100)


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


# --- Enums ---

class DocumentType(str, Enum):
    subscription = "subscription"
    receipt = "receipt"
    bill = "bill"
    warranty = "warranty"
    travel = "travel"
    unknown = "unknown"


class ActionType(str, Enum):
    cancel_subscription = "cancel_subscription"
    request_refund = "request_refund"
    return_item = "return_item"
    monitor_price = "monitor_price"
    warranty_reminder = "warranty_reminder"
    bill_increase_alert = "bill_increase_alert"
    trial_ending_alert = "trial_ending_alert"
    no_action = "no_action"


class ActionStatus(str, Enum):
    new = "new"
    reviewed = "reviewed"
    dismissed = "dismissed"
    completed = "completed"


class TonePreference(str, Enum):
    professional = "professional"
    friendly = "friendly"
    firm = "firm"
    assertive = "assertive"


class FieldConfidence(BaseModel):
    value: str | float | bool | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    explanation: str = ""


# --- Input schemas ---

class InputDocument(BaseModel):
    input_text: str = Field(min_length=10, max_length=50000)
    input_type: str = Field(default="paste", pattern="^(paste|file_upload)$")


ExtractionRequest = InputDocument


class LLMExtractionResult(BaseModel):
    merchant: FieldConfidence | None = None
    document_type: FieldConfidence | None = None
    amount: FieldConfidence | None = None
    currency: FieldConfidence | None = None
    purchase_date: FieldConfidence | None = None
    subscription_status: FieldConfidence | None = None
    renewal_date: FieldConfidence | None = None
    free_trial_end_date: FieldConfidence | None = None
    return_deadline: FieldConfidence | None = None
    cancellation_deadline: FieldConfidence | None = None
    warranty_end_date: FieldConfidence | None = None
    cancellation_policy: FieldConfidence | None = None
    refund_opportunity: FieldConfidence | None = None
    price_increased: FieldConfidence | None = None
    old_price: FieldConfidence | None = None
    new_price: FieldConfidence | None = None
    detected_risk: FieldConfidence | None = None
    recommended_action: FieldConfidence | None = None
    explanation: FieldConfidence | None = None


# --- Extraction response schemas ---

class ExtractedRecord(BaseModel):
    id: str
    merchant: str | None
    document_type: str | None
    amount: float | None
    currency: str | None
    purchase_date: date | None
    subscription_status: str | None
    renewal_date: date | None
    free_trial_end_date: date | None
    return_deadline: date | None
    cancellation_deadline: date | None
    warranty_end_date: date | None
    cancellation_policy: str | None
    refund_opportunity: str | None
    price_increased: bool | None
    old_price: float | None
    new_price: float | None
    detected_risk: str | None
    recommended_action: str | None
    explanation: str | None
    confidence_score: float | None
    field_confidences: dict | None = None
    is_duplicate: bool = False
    input_type: str
    created_at: datetime

    model_config = {"from_attributes": True}


ExtractionResponse = ExtractedRecord


class ActionCardResponse(BaseModel):
    id: str
    action_type: str
    title: str
    description: str | None
    urgency: str
    deadline: date | None
    status: str
    reminder_date: date | None = None
    completed_at: datetime | None = None
    savings_amount: float | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ExtractionWithActions(BaseModel):
    extraction: ExtractionResponse
    action_cards: list[ActionCardResponse]


class ExtractionListItem(BaseModel):
    id: str
    merchant: str | None
    document_type: str | None
    amount: float | None
    currency: str | None
    confidence_score: float | None
    input_type: str
    created_at: datetime
    action_count: int = 0

    model_config = {"from_attributes": True}


class PaginatedDocuments(BaseModel):
    items: list[ExtractionListItem]
    total: int
    page: int
    per_page: int
    pages: int


class ActionCardUpdate(BaseModel):
    status: ActionStatus | None = None
    reminder_date: date | None = None
    savings_amount: float | None = None


# --- Draft schemas ---

class DraftRequest(BaseModel):
    tone: TonePreference = TonePreference.professional


class EmailDraftResponse(BaseModel):
    id: str
    action_card_id: str
    subject: str
    body: str
    user_edited_body: str | None
    copied: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class EmailDraftUpdate(BaseModel):
    user_edited_body: str | None = None
    copied: bool | None = None


# --- Dashboard schemas ---

class DashboardResponse(BaseModel):
    total_savings: float
    documents_count: int
    actions_by_status: dict[str, int]
    completed_actions: int
    monthly_savings: list[dict]


class ErrorResponse(BaseModel):
    error: dict = Field(default_factory=lambda: {
        "code": "UNKNOWN_ERROR",
        "message": "An unexpected error occurred",
        "details": {},
    })
