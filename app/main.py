import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.models import Patient
from app.schemas import PatientCreate, PatientFields, PatientResponse, PatientUpdate, normalize_phone, parse_date_of_birth

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Patient Registration API", version="0.1.0", lifespan=lifespan)
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def success(data):
    return {"data": data, "error": None}


def serialize(patient: Patient) -> dict:
    return PatientResponse.model_validate(patient).model_dump(mode="json")


def get_active_patient(patient_id: UUID, database: Session) -> Patient:
    patient = database.scalar(
        select(Patient).where(Patient.patient_id == str(patient_id), Patient.deleted_at.is_(None))
    )
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return patient


@app.exception_handler(HTTPException)
async def http_error_handler(_: Request, error: HTTPException):
    return JSONResponse(
        status_code=error.status_code,
        content={"data": None, "error": {"code": "http_error", "message": str(error.detail)}},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, error: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "data": None,
            "error": {
                "code": "validation_error",
                "message": "Invalid request data",
                "details": jsonable_encoder(error.errors()),
            },
        },
    )


@app.get("/health")
def health_check():
    return success({"status": "ok"})


@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/patients")
def list_patients(
    last_name: str | None = None,
    date_of_birth: str | None = None,
    phone_number: str | None = None,
    database: Session = Depends(get_db),
):
    statement = select(Patient).where(Patient.deleted_at.is_(None)).order_by(Patient.created_at.desc())
    if last_name:
        statement = statement.where(Patient.last_name.ilike(last_name.strip()))
    if date_of_birth:
        try:
            statement = statement.where(Patient.date_of_birth == parse_date_of_birth(date_of_birth))
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
    if phone_number:
        try:
            statement = statement.where(Patient.phone_number == normalize_phone(phone_number))
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
    return success([serialize(patient) for patient in database.scalars(statement).all()])


@app.get("/patients/{patient_id}")
def get_patient(patient_id: UUID, database: Session = Depends(get_db)):
    return success(serialize(get_active_patient(patient_id, database)))


@app.post("/patients", status_code=status.HTTP_201_CREATED)
def create_patient(payload: PatientCreate, database: Session = Depends(get_db)):
    existing = database.scalar(
        select(Patient).where(Patient.phone_number == payload.phone_number, Patient.deleted_at.is_(None))
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An active patient already exists with this phone number")
    patient = Patient(**payload.model_dump())
    database.add(patient)
    database.commit()
    database.refresh(patient)
    logger.info("patient_registered patient_id=%s phone_number=%s", patient.patient_id, patient.phone_number)
    return success(serialize(patient))


@app.put("/patients/{patient_id}")
def update_patient(patient_id: UUID, payload: PatientUpdate, database: Session = Depends(get_db)):
    patient = get_active_patient(patient_id, database)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="Provide at least one field to update")

    current = {field: getattr(patient, field) for field in PatientFields.model_fields}
    validated = PatientCreate.model_validate(current | updates)
    if validated.phone_number != patient.phone_number:
        existing = database.scalar(
            select(Patient).where(
                Patient.phone_number == validated.phone_number,
                Patient.patient_id != patient.patient_id,
                Patient.deleted_at.is_(None),
            )
        )
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An active patient already exists with this phone number")
    for field, value in validated.model_dump().items():
        setattr(patient, field, value)
    database.commit()
    database.refresh(patient)
    logger.info("patient_updated patient_id=%s", patient.patient_id)
    return success(serialize(patient))


@app.delete("/patients/{patient_id}")
def delete_patient(patient_id: UUID, database: Session = Depends(get_db)):
    patient = get_active_patient(patient_id, database)
    patient.deleted_at = datetime.now(timezone.utc)
    database.commit()
    logger.info("patient_soft_deleted patient_id=%s", patient.patient_id)
    return success({"patient_id": patient.patient_id, "deleted": True})
