# Patient Registration Voice Agent

A small FastAPI service for a voice-based patient-registration agent. It validates and persists U.S. patient demographics in SQLite, exposes the required REST API, and includes a Vapi-ready prompt and create-patient tool definition.

## Architecture

```text
Caller -> Vapi phone number -> Vapi assistant (LLM/STT/TTS)
                                  | confirmed tool call
                                  v
                         FastAPI /patients -> SQLite persistent volume
```

The assistant owns conversational collection and confirmation. The API remains the source of truth for validation and persistence, so malformed tool calls cannot create invalid records.

## Run locally

Requires Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`; interactive OpenAPI documentation is at `/docs`.

```bash
pytest
curl http://127.0.0.1:8000/health
```

## API

Every endpoint responds with `{ "data": ..., "error": null }` on success and `{ "data": null, "error": { ... } }` on error.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/patients` | Lists active patients; supports `last_name`, `date_of_birth`, and `phone_number` filters. |
| `GET` | `/patients/{patient_id}` | Retrieves an active patient. |
| `POST` | `/patients` | Creates a patient after server-side validation. |
| `PUT` | `/patients/{patient_id}` | Partially updates a patient and revalidates the resulting record. |
| `DELETE` | `/patients/{patient_id}` | Soft-deletes a patient. |

Example request:

```bash
curl -X POST http://127.0.0.1:8000/patients \
  -H 'content-type: application/json' \
  -d '{
    "first_name":"Jane", "last_name":"Doe", "date_of_birth":"05/12/1990",
    "sex":"Female", "phone_number":"202-555-0148", "address_line_1":"123 Main St",
    "city":"Washington", "state":"DC", "zip_code":"20001"
  }'
```

## Configure Vapi

1. Deploy this service first and set `DATABASE_URL` to a SQLite file on the host's persistent disk, for example `sqlite:////var/data/patients.db`.
2. In Vapi, create an assistant and paste [the system prompt](docs/vapi-system-prompt.md) into its system message.
3. Add a server URL function tool for `POST https://YOUR-API/patients`. Use [the tool schema](docs/vapi-tool.json), replacing the placeholder URL. Configure it to pass the JSON body directly to the endpoint.
4. Provision a U.S. number in Vapi and attach it to this assistant. Test in the Vapi simulator before placing a phone call.
5. Set the deployed API URL and dialable number below before submission.

| Deployment detail | Value |
| --- | --- |
| API base URL | `TODO` |
| Phone number | `TODO` |

## Environment variables

| Variable | Required | Description |
| --- | --- | --- |
| `DATABASE_URL` | No | Defaults to `sqlite:///./data/patients.db`. Production must point at persistent storage. |
| `ALLOWED_ORIGINS` | No | Reserved for a browser dashboard; not needed by Vapi server tools. |

## Trade-offs and limitations

- SQLite is the fastest dependable choice for a single-instance demo. Use PostgreSQL and migrations for concurrent production deployments.
- The API logs registration IDs and phone numbers to stdout for the requested observability. Do not use these logs or this demo configuration for real protected health information without a compliant operational design.
- Vapi credentials are intentionally configured in Vapi, not committed to this repository. Add request authentication before exposing the API beyond the assessment environment.
