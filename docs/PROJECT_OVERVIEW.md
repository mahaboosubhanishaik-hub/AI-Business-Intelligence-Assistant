# Project Overview

## What this project does

The AI Business Intelligence Assistant is a Flask web application for business
users to upload tabular data, inspect its quality, review business metrics, and
ask questions grounded in dataset summaries. It also provides administrators
with account-management tools and gives business users budget, comparison, and
monthly reporting workflows.

The application renders server-side Jinja templates, uses Pandas for dataset
processing, persists account and audit metadata through SQLAlchemy, and uses
Chart.js for interactive charts. Google Gemini is optional; the application
uses deterministic summaries when the API is not configured and reports that
the question-answering assistant is unavailable.

## Main capabilities

### Business user

1. Register and sign in with a business handle or email.
2. Upload CSV or Excel datasets. Uploads are size-limited, parsed and validated,
   assigned server-generated filenames, and associated with the owning account.
3. Browse datasets, preview rows, and review column profiles and quality issues.
4. Open analytics dashboards for available revenue, profit, quantity, product,
   region, category, and date fields.
5. Ask natural-language questions about the available structured dataset
   context, or review generated summaries and recommendations.
6. Configure monthly budgets, compare measures by group or period, and view
   monthly reports.
7. Search and filter analysis history and export account-scoped history as CSV.
8. Manage profile details and change the account password. Clients can edit
   their business handle; administrators can edit their business handle and
   email from profile settings.

### Administrator

- Sign in through the separate `/admin/login` route.
- Review account, dataset, analysis, and recent activity summaries.
- Activate or deactivate business accounts.
- Issue a generated temporary password to an existing active business account.
  The password is shown once, expires, and requires a password change after
  sign-in.
- Update the administrator's name, business handle, email, and password.

## Application flow

```text
Browser
  -> Flask route and authentication/ownership checks
  -> SQLAlchemy metadata lookup and upload-file load
  -> profiling, quality, analytics, reporting, or AI service
  -> database audit/activity records where applicable
  -> Jinja page, chart data, or CSV response
```

Uploaded file contents are stored under `uploads/`; the database stores account
and dataset metadata, not a copy of the complete table. Data routes verify
dataset ownership before reading or deleting an upload. The quality monitor
stores audit snapshots so later inspections can be compared with previous
scores.

For Gemini requests, the AI service builds structured context from dataset
metadata, column names, data-quality results, business KPIs, highlights, chart
aggregates, and numeric statistics. It does not construct a prompt by dumping
the entire raw dataset. The service instructs the model to answer only from the
provided evidence.

## Code map

```text
app/
  __init__.py                 Flask application factory, extensions, middleware
  decorators.py               Role access decorators
  models/
    user.py                   Accounts, roles, password and login state
    dataset.py                Dataset ownership and upload metadata
    activity_log.py           Account and administrative activity
    quality_audit.py          Historical quality snapshots
    monthly_budget.py         User- and dataset-scoped budgets
  routes/
    __init__.py               Public landing page, dashboard, analysis history
    auth.py                   Registration, login, profile, password changes
    admin.py                  Administrator login and account management
    data.py                   Uploads, previews, profiling, quality, deletion
    analytics.py              Business analytics dashboards
    ai.py                     Dataset-grounded AI assistant
    reports.py                Budgets, comparisons, monthly reports
  services/
    data_loader.py            CSV/Excel parsing and input checks
    data_profiler.py          Dataset and column profiling
    data_quality.py           Quality scoring and issue detection
    monitoring.py             Audit snapshots and quality alerts
    analytics.py              KPI, chart, and business-highlight aggregation
    business_metrics.py       Budget and comparison calculations
    ai_service.py             Gemini context, summaries, and Q&A
    auth_security.py          Login lockout helpers
    activity_log.py           Activity-recording helper
    email.py                  SMTP delivery helper
  templates/                  Jinja pages and error screens
  static/                     CSS, JavaScript, and image assets
config.py                     Environment-backed application configuration
app.py                        WSGI object and local development entry point
migrations/                   Alembic/Flask-Migrate history
tests/                        Unit and integration test suites
uploads/                      Runtime dataset files; treat as user data
instance/                     Local instance data such as SQLite databases
reports/                      Report output directory
docs/PROJECT_OVERVIEW.md      This architecture and operations guide
README.md                     Project introduction and quick setup
Procfile                      Platform web-process command
gunicorn.conf.py              Gunicorn worker and server configuration
requirements.txt               Python dependencies
```

### Application layers

- **Factory and extensions:** `app/__init__.py` initializes Flask-Login,
  SQLAlchemy, Flask-Migrate, CSRF protection, rate limiting, request hooks,
  security headers, error pages, and route blueprints.
- **Routes:** authenticate requests, enforce roles and account ownership, call
  services, and choose templates or response formats.
- **Services:** perform file parsing, profiling, quality evaluation, KPI
  aggregation, report calculations, AI context construction, and shared
  authentication/activity operations.
- **Models:** persist user, dataset, audit, budget, and activity records.
- **Templates and static assets:** provide the Bootstrap-based interface,
  client-side chart rendering, and responsive styling.
- **Migrations:** evolve persistent schemas. Apply migrations rather than
  relying on `create_all()` for deployment databases.

## Data and persistence

| Model/table | Purpose |
| --- | --- |
| `User` / `users` | Name, unique business handle and email, role, active state, password hash, and temporary-password/login-lock state. |
| `Dataset` / `datasets` | Upload metadata, owner, source type, dimensions, and file size. |
| `QualityAudit` / `quality_audits` | Dated quality score, status, and issue counts for a dataset and owner. |
| `MonthlyBudget` / `monthly_budgets` | User-scoped budget amount and the dataset columns/group it applies to. |
| `ActivityLog` / `activity_logs` | Timestamped account, dataset, analysis, and administrator events. |

`DATABASE_URL` selects the database connection. PostgreSQL is suitable for
deployment; SQLite can be used for local development by setting a SQLite URL.
Uploaded files are separate from database records, so deployments should
preserve and back up the upload storage as well as the database.

## Quality and analytics behavior

- Profiling identifies common column types and produces summaries suited to
  numeric, categorical, and date-like values.
- Data quality evaluates completeness, uniqueness, validity, and consistency.
  It reports missing values, duplicate rows, empty strings, suspicious
  negative business measures, and numeric outliers.
- Quality scores are classified as Excellent, Good, Needs Attention, or Poor.
  Repeated audits are persisted and can produce degradation and threshold
  alerts.
- Analytics maps likely business columns by name, then computes applicable
  financial KPIs, highlights, and chart series. Datasets without matching
  columns may not provide every KPI or chart.
- Budget and comparison views let users select dataset columns and date/group
  scopes rather than requiring one fixed upload schema.

## Configuration

Create a private `.env` file in the project root (do not commit it). Common
settings are:

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | Flask session and security signing key. Required in production. |
| `DATABASE_URL` | SQLAlchemy database URL, such as a PostgreSQL connection or `sqlite:///instance/app.db`. |
| `ADMIN_USERNAME` | Initial administrator sign-in handle; defaults to `@admin`. |
| `ADMIN_EMAIL` | Initial administrator email; defaults to `admin@localhost`. |
| `ADMIN_PASSWORD` | Initial administrator password; the development default must not be used in production. |
| `GEMINI_API_KEY` | Optional Google Gemini key for summaries and question answering. |
| `SESSION_COOKIE_SECURE` | Set to `true` when the application is served over HTTPS. |
| `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USE_TLS`, `MAIL_USE_SSL`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_DEFAULT_SENDER` | Optional SMTP delivery configuration. |
| `PORT`, `WEB_CONCURRENCY`, `LOG_LEVEL` | Gunicorn runtime settings. |

The initial administrator is provisioned on the first request when no admin
account exists. Once created, changing the configured seed credentials does
not reset that account. Existing administrator profile changes persist across
application restarts.

## Local development (Windows PowerShell)

Run these commands from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` with a valid local `DATABASE_URL`, `SECRET_KEY`, and administrator
credentials. For SQLite, create the `instance` directory if it is missing and
use `DATABASE_URL=sqlite:///instance/app.db`. Keep real credentials and
production database URLs out of source control.

Apply database migrations and start the development server:

```powershell
python -m flask --app app db upgrade
python app.py
```

The local server listens at `http://127.0.0.1:5000`. For a production-style
local launch, use:

```powershell
gunicorn --config gunicorn.conf.py app:app
```

## Tests

Run the phase-based data and application tests:

```powershell
python -m unittest tests/test_phase1.py tests/test_phase2.py tests/test_phase3.py tests/test_phase4.py tests/test_phase5.py tests/test_phase6.py
```

Run authentication, role, data, analyst, and business-report tests as needed:

```powershell
python -m unittest tests.test_auth tests.test_role_auth tests.test_data tests.test_analyst tests.test_business_reports
```

Point `DATABASE_URL` at a disposable local test database before running tests.
Never run test setup or destructive test cases against a production database.

## Deployment and operations

The `Procfile` starts Gunicorn using `gunicorn.conf.py`. Configure production
secrets, a reachable database, a strong administrator password, and secure
session cookies before deployment. Apply migrations before serving traffic.
Persist and back up both the database and uploaded files; do not expose
`uploads/`, `.env`, or database files as public static content.

For short setup instructions and the feature summary, see the root
[README](../README.md).
