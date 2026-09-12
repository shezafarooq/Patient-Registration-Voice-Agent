import re
from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator, model_validator

NAME_PATTERN = re.compile(r"^[A-Za-z]+(?:[ '-][A-Za-z]+)*$")
MEMBER_ID_PATTERN = re.compile(r"^[A-Za-z0-9-]+$")
ZIP_PATTERN = re.compile(r"^\d{5}(?:-\d{4})?$")
US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY",
    "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND",
    "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
}
OPTIONAL_STRING_FIELDS = {
    "email",
    "address_line_2",
    "insurance_provider",
    "insurance_member_id",
    "emergency_contact_name",
    "emergency_contact_phone",
}


class Sex(str, Enum):
    male = "Male"
    female = "Female"
    other = "Other"
    decline = "Decline to Answer"


def normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10 or digits[0] in "01" or digits[3] in "01":
        raise ValueError("must be a valid 10-digit U.S. phone number")
    return digits


def parse_date_of_birth(value: str | date) -> date:
    if isinstance(value, date):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.strptime(value.strip(), "%m/%d/%Y").date()
        except ValueError:
            try:
                parsed = date.fromisoformat(value.strip())
            except ValueError as error:
                raise ValueError("must use MM/DD/YYYY") from error
    else:
        raise ValueError("must use MM/DD/YYYY")
    if parsed > date.today():
        raise ValueError("cannot be in the future")
    return parsed


class PatientFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: str
    last_name: str
    date_of_birth: date
    sex: Sex
    phone_number: str
    email: EmailStr | None = None
    address_line_1: str
    address_line_2: str | None = None
    city: str
    state: str
    zip_code: str
    insurance_provider: str | None = None
    insurance_member_id: str | None = None
    preferred_language: str = "English"
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_empty_optional_fields(cls, values: object) -> object:
        if not isinstance(values, dict):
            return values
        return {
            key: None if key in OPTIONAL_STRING_FIELDS and isinstance(value, str) and not value.strip() else value
            for key, value in values.items()
        }

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not 1 <= len(value) <= 50 or not NAME_PATTERN.fullmatch(value):
            raise ValueError("must be 1-50 letters and may include spaces, hyphens, or apostrophes")
        return value

    @field_validator("date_of_birth", mode="before")
    @classmethod
    def validate_date_of_birth(cls, value: str | date) -> date:
        return parse_date_of_birth(value)

    @field_validator("phone_number", "emergency_contact_phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        return None if value is None else normalize_phone(value)

    @field_validator("address_line_1", "city")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be empty")
        return value

    @field_validator("address_line_1")
    @classmethod
    def validate_address_length(cls, value: str) -> str:
        if len(value) > 200:
            raise ValueError("must be at most 200 characters")
        return value

    @field_validator("city")
    @classmethod
    def validate_city_length(cls, value: str) -> str:
        if len(value) > 100:
            raise ValueError("must be at most 100 characters")
        return value

    @field_validator("state")
    @classmethod
    def validate_state(cls, value: str) -> str:
        value = value.strip().upper()
        if value not in US_STATES:
            raise ValueError("must be a valid 2-letter U.S. state abbreviation")
        return value

    @field_validator("zip_code")
    @classmethod
    def validate_zip_code(cls, value: str) -> str:
        value = value.strip()
        if not ZIP_PATTERN.fullmatch(value):
            raise ValueError("must be a 5-digit ZIP code or ZIP+4")
        return value

    @field_validator("insurance_member_id")
    @classmethod
    def validate_member_id(cls, value: str | None) -> str | None:
        if value is not None and not MEMBER_ID_PATTERN.fullmatch(value.strip()):
            raise ValueError("must be alphanumeric and may include hyphens")
        return value.strip() if value else None

    @field_validator("preferred_language")
    @classmethod
    def validate_language(cls, value: str) -> str:
        value = value.strip()
        if not value or len(value) > 100:
            raise ValueError("must be 1-100 characters")
        return value


class PatientCreate(PatientFields):
    pass


class PatientUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: str | None = None
    last_name: str | None = None
    date_of_birth: str | date | None = None
    sex: Sex | None = None
    phone_number: str | None = None
    email: EmailStr | None = None
    address_line_1: str | None = None
    address_line_2: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    insurance_provider: str | None = None
    insurance_member_id: str | None = None
    preferred_language: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_empty_optional_fields(cls, values: object) -> object:
        if not isinstance(values, dict):
            return values
        return {
            key: None if key in OPTIONAL_STRING_FIELDS and isinstance(value, str) and not value.strip() else value
            for key, value in values.items()
        }


class PatientResponse(PatientFields):
    model_config = ConfigDict(from_attributes=True)

    patient_id: str
    created_at: datetime
    updated_at: datetime


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: list[dict] | None = None


class ErrorEnvelope(BaseModel):
    data: None = None
    error: ErrorDetail
