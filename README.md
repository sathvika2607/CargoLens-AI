# CargoLens AI — Intelligent Customs Documentation & Verification Platform

CargoLens AI is an AI-assisted document extraction, cross-document reconciliation, and verification platform designed for customs brokers and international freight forwarders.

The platform helps documentation teams process commercial invoices, packing lists, and bills of lading, identify inconsistencies across documents, review extracted information, and prepare verified shipment data for CSV export.

**Project context:** Customs documentation operations at Nhava Sheva (JNPT), Navi Mumbai, India.

---

## 1. Technology Stack

| Layer | Technologies |
|---|---|
| Frontend | React 18, TypeScript, Vite |
| UI | Tailwind CSS, Lucide React |
| Data fetching | TanStack Query, Axios |
| Backend | Python 3.12, FastAPI, Pydantic |
| Database | PostgreSQL 16 |
| ORM | SQLAlchemy 2 (Async) |
| Migrations | Alembic |
| Authentication | JWT-based authentication |
| Document processing | PDF processing, OCR pipeline, text extraction |
| AI integration | Provider-based extraction architecture, Anthropic integration, fixture provider |
| Testing | Pytest, Vitest |
| Containerization | Docker, Docker Compose |

---

## 2. Core Features

### Document Management and Extraction
- Manage shipment documentation.
- Upload and process commercial invoices, packing lists, and bills of lading.
- Extract structured information from trade documents.
- View PDF pages and extracted information.
- Review extraction confidence and supporting evidence.

### Cross-Document Validation
- Compare corresponding information across shipment documents.
- Detect weight, quantity, financial, and documentation inconsistencies.
- Identify missing documents and incomplete information.
- Apply deterministic validation rules and configurable tolerances.
- Preserve missing values rather than silently inventing extracted information.

### Human Review and Verification
- Review extracted fields and discrepancies.
- Correct information through documented review actions.
- Maintain reviewer attribution and audit history.
- Require verification checks before allowing eligible exports.

### Shared Workspace and Role-Based Access
- Registered documentation executives and managers access the shared operational workspace.
- Self-registration assigns the documentation executive role.
- Manager-only operations include team administration and simulation controls.
- Privileged operations are protected by backend authorization checks.

### Analytics and Reporting
- Shipment and document status summaries.
- Daily, weekly, and monthly shipment activity.
- Document processing and discrepancy statistics.
- Audit and export activity.
- CSV export for eligible verified shipments.

### Demonstration and Simulation
- Synthetic demonstration shipments and documents.
- Controlled scenarios for missing information, discrepancies, and incomplete document sets.
- Demonstration records are labelled as synthetic and are not real customs submissions or human approvals.

---

## 3. Project Structure

```text
CargoLens AI/
|
|-- cargolens-api/
|   |-- app/
|   |   |-- api/                 # API dependencies and versioned routes
|   |   |-- cli/                 # Demo data and utilities
|   |   |-- models/              # SQLAlchemy database models
|   |   |-- schemas/             # Pydantic request and response schemas
|   |   |-- services/            # Application business logic
|   |   |   |-- ai/              # AI provider integrations
|   |   |   |-- documents/       # Document generation
|   |   |   |-- export/          # CSV export
|   |   |   |-- ocr/             # OCR and PDF processing
|   |   |   |-- simulation/      # Demonstration scenarios
|   |   |   |-- validation/      # Validation engine and rules
|   |   |-- storage/             # Document storage services
|   |   |-- config.py
|   |   |-- database.py
|   |   |-- main.py
|   |   |-- security.py
|   |-- alembic/                 # Database migrations
|   |-- tests/                   # Backend automated tests
|   |-- .dockerignore
|   |-- .env.example
|   |-- Dockerfile
|   |-- docker-compose.yml
|   |-- requirements.txt
|   |-- pyproject.toml
|
|-- cargolens-ui/
|   |-- src/
|   |   |-- api/                 # Typed API clients
|   |   |-- components/          # Reusable UI components
|   |   |-- context/             # Authentication context
|   |   |-- pages/               # Application screens
|   |   |-- test/                # Frontend tests
|   |   |-- types/               # TypeScript interfaces
|   |-- index.html
|   |-- package.json
|   |-- vite.config.ts
|
|-- .gitignore
|-- README.md
```

Runtime documents, local environment files, database data, and generated artifacts are intentionally excluded from Git.

---

## 4. Prerequisites

- Windows 10/11, Linux, or macOS
- Python 3.12
- Node.js 18 or later
- npm
- Docker Desktop with Docker Compose
- PostgreSQL 16 if running without Docker

---

## 5. Local Development Setup

### 5.1 Clone the repository

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
cd "CargoLens AI"
```

### 5.2 Configure the backend environment

Open a CMD terminal and navigate to the backend:

```cmd
cd cargolens-api
```

Copy the environment template:

```cmd
copy .env.example .env
```

Open `.env` and replace all example secret and database placeholders with your own local values.

Never commit the `.env` file.

### 5.3 Start PostgreSQL

From the `cargolens-api` directory:

```cmd
docker compose up -d
```

Check the database container:

```cmd
docker compose ps
```

The PostgreSQL service uses a named Docker volume to preserve database data across container restarts.

### 5.4 Install backend dependencies

From the `cargolens-api` directory:

```cmd
python -m venv .venv
```

Activate the virtual environment:

```cmd
.venv\Scripts\activate
```

Install dependencies:

```cmd
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 5.5 Apply database migrations

From the `cargolens-api` directory:

```cmd
alembic upgrade head
```

### 5.6 Start the backend

```cmd
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Backend URL:

`http://127.0.0.1:8000`

Interactive API documentation:

`http://127.0.0.1:8000/docs`

### 5.7 Start the frontend

Open a second CMD terminal:

```cmd
cd cargolens-ui
```

Install frontend dependencies:

```cmd
npm install
```

Start the development server:

```cmd
npm run dev
```

Frontend URL:

`http://localhost:5173`

Build the frontend:

```cmd
npm run build
```

---

## 6. Authentication and Access Control

CargoLens AI uses JWT-based authentication and role-based authorization.

- Users can register through the application.
- New self-registered accounts receive the documentation executive role.
- Managers can access additional administration and simulation functionality.
- Privileged operations are protected by backend authorization.
- Authorized users share the same operational demonstration workspace.

Manager privileges cannot be obtained by submitting a different role during public registration.

---

## 7. Document Processing and Verification Workflow

The main shipment documentation workflow includes:

1. Access a shipment in the shared workspace.
2. Upload or inspect its supporting trade documents.
3. Process documents and extract structured fields.
4. Review extracted values and supporting evidence.
5. Run cross-document validation.
6. Investigate discrepancies and missing information.
7. Correct fields through human review actions.
8. Complete the required verification checks.
9. Export eligible verified shipment information to CSV.
10. Review the associated audit and export history.

The platform distinguishes extracted information, computed guidance, demonstration fixtures, and genuine human review actions.

---

## 8. Automated Testing

CargoLens AI maintains separate backend and frontend test suites.

### 8.1 Backend tests

Backend tests must use the isolated test database `cargolens_test_db`, never the application database `cargolens_db`.

Create the dedicated test database if it does not already exist:

```cmd
docker exec cargolens-postgres psql -U cargolens_user -d postgres -c "CREATE DATABASE cargolens_test_db OWNER cargolens_user;"
```

Set the test database connection in CMD, replacing the password placeholder with your local database password:

```cmd
set CARGOLENS_TEST_DATABASE_URL=postgresql+asyncpg://cargolens_user:YOUR_LOCAL_PASSWORD@127.0.0.1:5432/cargolens_test_db
```

Run backend tests:

```cmd
cd cargolens-api
.venv\Scripts\pytest.exe -v --tb=short
```

The test database isolation guard prevents automated tests from running against the application database.

### 8.2 Frontend tests

From the `cargolens-ui` directory:

```cmd
npm test
```

If the project provides a dedicated CI test script:

```cmd
npm run test:run
```

### 8.3 Production build verification

```cmd
npm run build
```

---

## 9. Document Storage

Uploaded and generated documents are stored separately from the source code.

The current local storage configuration uses:

- `STORAGE_BACKEND=local`
- `STORAGE_LOCAL_DIR=storage/documents`

The document storage directory is excluded from Git.

For deployment, configure persistent document storage. Do not rely on an ephemeral container filesystem for uploaded documents.

When migrating the demonstration workspace, transfer the required demonstration PDFs and preserve their corresponding database storage keys.

---

## 10. AI Provider Configuration and Limitations

The application includes a provider-based AI extraction architecture with an Anthropic integration and a fixture provider for controlled demonstration and testing.

A valid Anthropic API key is required for real Anthropic-powered inference.

When the API key is not configured, the application may use the configured fixture or demonstration provider. Fixture-based output must not be represented as live AI inference.

AI-extracted information is subject to validation and human review. AI output alone does not constitute customs approval or a legally verified declaration.

---

## 11. Security Considerations

- Passwords are securely hashed.
- Authentication uses JWT-based access control.
- New self-registered accounts receive the documentation executive role.
- Manager-only operations require backend authorization.
- Sensitive environment files are excluded from Git.
- Docker build context excludes local secrets and runtime documents.
- Automated tests use a physically isolated test database.
- Demonstration records are distinguished from genuine human review actions.

Before public deployment, configure production secrets, allowed CORS origins, database access restrictions, HTTPS, and persistent document storage.

Do not publish demonstration credentials or reuse local development credentials in production.

---

## 12. Important Notes

- Demonstration shipments and trade documents contain synthetic data.
- Demonstration documents are not official customs documents.
- Demonstration audit fixtures are not genuine human approvals.
- CSV export eligibility is governed by application verification and review rules.
- Real AI inference depends on the selected provider and valid provider configuration.
- Local document storage must be replaced with an appropriate persistent deployment solution before production use.

---

## 13. Verification Status

The project has undergone local functional, security, data-integrity, and regression verification.

The latest recorded local verification included:

- 135 unique backend tests passed.
- 41 frontend tests passed.
- Frontend production build completed successfully.
- Authentication and role-based access checks verified.
- Shared workspace visibility verified.
- Demonstration discrepancy and missing-information scenarios verified.
- Database isolation and preservation checks completed.

These results describe local verification and do not imply that public production deployment has already been completed.

---

**CargoLens AI — Intelligent Documentation. Reliable Validation. Human-Verified Decisions.**