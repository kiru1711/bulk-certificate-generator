# Bulk Certificate Generator API

A beginner friendly FastAPI service that accepts one batch of recipients, creates a PDF certificate for each valid recipient, records progress in SQLite, and serves individual PDFs or a ZIP of successful certificates.

## Features and technology

- Python 3.10 or newer, FastAPI, Pydantic, SQLAlchemy, and SQLite
- ReportLab PDF output using one built in certificate design
- Independent recipient outcomes: blank names and malformed email addresses are recorded as failures while other recipients continue
- In process background execution with job and recipient progress saved to the database
- Individual PDF and ZIP downloads

## Project layout

```text
app/                  API application and business logic
  main.py             Application startup and health endpoint
  database.py         SQLite engine and sessions
  models.py           Job and recipient tables
  schemas.py          Request and response validation
  routes.py           HTTP endpoints
  services.py         Job creation and background processing
  certificate.py      ReportLab certificate design
  storage.py          Safe output paths and ZIP creation
tests/                API tests using a temporary SQLite database
frontend/             Responsive browser interface (HTML, CSS, vanilla JS)
generated_certificates/ Generated output (created as needed)
```

## Setup on Windows PowerShell

Run these commands from the project folder:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks virtual environment activation, use `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that terminal, then activate again.

Start the server:

```powershell
uvicorn app.main:app --reload
```

Open the frontend at `http://127.0.0.1:8000/` and Swagger UI at `http://127.0.0.1:8000/docs`. The health endpoint is `GET /health`.

## Use the web interface

The frontend is served from the same FastAPI application as the API, so it uses the same origin and does not need CORS configuration. Start the server with the command above, then open `http://127.0.0.1:8000/`. Fill in the certificate details, add or remove recipient rows, and choose **Generate certificates**. The page submits the full list in one request, polls the returned job until it finishes, and shows progress and per-recipient outcomes. Successful recipients have individual PDF download links; **Download all (.zip)** downloads the successful certificates together.

The API base URL is set in `frontend/script.js` as `window.BULK_CERT_API_BASE_URL || window.location.origin`. For the normal local setup, FastAPI serves both the page and API at `http://127.0.0.1:8000`. If you host the static files separately, set `window.BULK_CERT_API_BASE_URL` to the API origin before loading `script.js` and configure the API's CORS policy for that static page origin.

The frontend uses only local assets and browser APIs. There is no separate frontend install or build step.

The app reads these optional process environment variables directly; no `.env` loader is used:

- `DATABASE_URL` defaults to `sqlite:///./bulk_certificates.db`
- `OUTPUT_DIR` defaults to `./generated_certificates`
- `MAX_BATCH_SIZE` defaults to `500`

For example, set a custom output directory for the current PowerShell session with `$env:OUTPUT_DIR = "D:\certificates"` before starting Uvicorn.

## Create a job

Send `POST /api/v1/jobs`. The title, event, and issuer are nonempty strings up to 200 characters. The issue date uses `YYYY-MM-DD`. Supply 1 to 500 recipients by default; each has a name and optional email. A blank name or malformed email is treated as an individual recipient failure.

```json
{
  "certificate_title": "Certificate of Completion",
  "event_name": "Python Workshop",
  "issuer_name": "ABC Organization",
  "issue_date": "2026-10-12",
  "recipients": [
    {"name": "Alice Johnson", "email": "alice@example.com"},
    {"name": "Bob Smith"}
  ]
}
```

The API returns HTTP `202` with a `job_id` and initial status. Use the following PowerShell example (replace the URL as needed):

```powershell
$body = Get-Content .\request.json -Raw
$job = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/jobs -ContentType 'application/json' -Body $body
$job.job_id
```

## Check progress and download certificates

- `GET /api/v1/jobs/{job_id}` returns overall status, totals, success/failure/pending counts, timestamps, and per-recipient results.
- A finished job is `completed` when all recipients succeed, `completed_with_errors` when some succeed and some fail, and `failed` when none succeed. While work runs, it is `processing`.
- `GET /api/v1/jobs/{job_id}/certificates/{recipient_id}` downloads one successful PDF.
- `GET /api/v1/jobs/{job_id}/certificates` downloads a ZIP containing available successful PDFs only.

Download examples:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/v1/jobs/$($job.job_id)/certificates -OutFile .\certificates.zip
Invoke-WebRequest http://127.0.0.1:8000/api/v1/jobs/$($job.job_id)/certificates/RECIPIENT_ID -OutFile .\certificate.pdf
```

## Run tests

```powershell
python -m pytest -q
```

Tests use a temporary SQLite database and output directory. The FastAPI test client runs background tasks before returning, which makes the job results deterministic in tests.

## Design and limitations

The API stores each job and recipient in SQLite. FastAPI `BackgroundTasks` calls a separate worker function that opens and closes its own SQLAlchemy session. The worker processes recipients one at a time and commits each outcome, so an individual generation error does not stop the rest of the batch. Certificate filenames are generated by the server from UUIDs; path construction checks that files stay inside the configured output folder.

This in process worker is intentionally simple. An application restart can interrupt active jobs, and there is no durable queue or automatic retry. It is suitable for this assignment, not for production workloads that need guaranteed processing.
