# Health Prediction Application

React frontend with a Python Flask REST API, SQLite persistence, Groq-generated preliminary assessments, and separate MedlinePlus health-topic references.

## Project layout

```text
backend/
  app.py                 Flask REST API
  database.py            SQLite CRUD and assignment seed guard
  dataset.py             Exact original assignment rows
  groq_service.py        Groq chat-completion integration
  medlineplus.py         MedlinePlus Web Service integration
  validation.py          Email, date, and numeric validation
  health_records.sqlite3 Existing patient database (preserved)
frontend/
  src/                   React application and CSS
  package.json           Frontend dependencies and scripts
  vite.config.js         Development proxy to Flask
```

## Backend setup

Run these commands from the project root in PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

Add your Groq key to `backend/.env` as `GROQ_API_KEY=...` if it is not already configured, then start Flask:

```powershell
python app.py
```

Flask listens at `http://127.0.0.1:5000`. The existing database file is located beside the backend code and is not reset on startup. On a genuinely new database only, the original dataset is validated and imported once; duplicates are allowed and invalid rows are returned separately.

## Frontend setup

Open a second terminal from the project root:

```powershell
cd frontend
npm install
npm run dev
```

Open the Vite URL shown in the terminal, normally `http://127.0.0.1:5173`. Vite proxies `/api` requests to Flask. For a separately hosted frontend, set `FRONTEND_ORIGIN` in the backend environment to its origin.

To create a static frontend build, run `npm run build` in `frontend`; the output is written to `frontend/dist`.

## REST API

- `GET /api/health`
- `GET /api/patients`, `GET /api/patients/<id>`
- `POST /api/patients`, `PUT /api/patients/<id>`, `DELETE /api/patients/<id>`
- `GET /api/assignment/rejected`
- `GET /api/medlineplus`

Validation errors return HTTP 400 with field-specific messages. Patient names, email addresses, and dates of birth are never sent to Groq; only the three lab values are included in its assessment request. MedlinePlus references are presented separately from the AI Remarks sections.
