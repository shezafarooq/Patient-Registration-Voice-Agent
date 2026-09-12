import os

# Never let tests use the deployment database configured in .env.
# This temporary file is outside the repository and is never used by the app.
os.environ["DATABASE_URL"] = "sqlite:////tmp/patient-registration-agent-test.db"

from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app

client = TestClient(app)


def patient_payload():
    return {
        "first_name": "Jane", "last_name": "O'Connor", "date_of_birth": "05/12/1990", "sex": "Female",
        "phone_number": "(202) 555-0148", "email": "jane@example.com", "address_line_1": "123 Main Street",
        "city": "Washington", "state": "dc", "zip_code": "20001",
    }


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    engine.dispose()


def test_create_and_retrieve_patient():
    created = client.post("/patients", json=patient_payload())
    assert created.status_code == 201
    record = created.json()["data"]
    assert record["phone_number"] == "2025550148"
    retrieved = client.get(f"/patients/{record['patient_id']}")
    assert retrieved.status_code == 200
    assert retrieved.json()["data"]["last_name"] == "O'Connor"


def test_last_name_filter_supports_partial_case_insensitive_search():
    client.post("/patients", json=patient_payload())
    response = client.get("/patients", params={"last_name": "conn"})
    assert response.status_code == 200
    assert response.json()["data"][0]["last_name"] == "O'Connor"


def test_dashboard_is_served_from_the_api():
    response = client.get("/")
    assert response.status_code == 200
    assert "Patient Registry" in response.text
    assert "Add patient" in response.text
    assert client.get("/static/dashboard.js").status_code == 200


def test_invalid_future_dob_returns_envelope():
    response = client.post("/patients", json=patient_payload() | {"date_of_birth": "01/01/2999"})
    assert response.status_code == 422
    assert response.json()["data"] is None
    assert response.json()["error"]["code"] == "validation_error"


def test_empty_optional_tool_values_are_stored_as_null():
    response = client.post(
        "/patients",
        json=patient_payload() | {
            "email": "",
            "address_line_2": "   ",
            "insurance_provider": "",
            "insurance_member_id": "",
            "preferred_language": "   ",
            "emergency_contact_name": "",
            "emergency_contact_phone": "",
        },
    )
    assert response.status_code == 201
    record = response.json()["data"]
    assert all(record[field] is None for field in (
        "email",
        "address_line_2",
        "insurance_provider",
        "insurance_member_id",
        "emergency_contact_name",
        "emergency_contact_phone",
    ))
    assert record["preferred_language"] == "English"


def test_soft_deleted_patient_is_not_listed():
    created = client.post("/patients", json=patient_payload()).json()["data"]
    assert client.delete(f"/patients/{created['patient_id']}").status_code == 200
    assert client.get(f"/patients/{created['patient_id']}").status_code == 404
    assert client.get("/patients").json()["data"] == []
