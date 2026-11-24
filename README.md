# AI Business Intelligence Assistant

An enterprise-grade, data-grounded Business Intelligence (BI) platform combining automated dataset management, data profiling, Data Quality Monitoring (DQM), financial business analytics, interactive Chart.js visualizations, and an AI Business Intelligence Assistant powered by Google Gemini.

---

## 🚀 Purpose

The **AI Business Intelligence Assistant** enables business users and decision-makers to effortlessly upload datasets (CSV or Excel), evaluate dataset health, inspect financial KPIs, visualize multi-dimensional performance metrics, track data quality degradation over time, and interact with an AI assistant for data-grounded insights and executive recommendations.

For the full project structure, architecture, data flow, configuration, and operations guide, see [Project Overview](docs/PROJECT_OVERVIEW.md).

---

## ✨ Key Features

1. **Dataset Management & Storage**
   - Upload CSV (`.csv`) and Excel (`.xlsx`, `.xls`) files.
   - Enforces 50MB file size limits, non-empty validation, and encoding fallbacks (`utf-8`, `latin-1`, `iso-8859-1`).
   - Secure UUID-based physical storage to prevent path traversal and overwrite vulnerabilities.
   - Per-dataset 50-row interactive data preview.

2. **Intelligent Data Profiling**
   - Dataset-level memory estimation and cell metrics.
   - Smart column type classification (`integer`, `float`, `boolean`, `datetime`, `string`).
   - Column-level statistics: Min, Max, Mean, Median, Standard Deviation for numeric columns; Mode & Frequency for categorical columns; Date ranges for datetime columns.

3. **Data Quality Monitoring (DQM)**
   - Evaluates dataset quality across **4 Quality Dimensions**:
     - **Completeness (30%)**: Missing value ratio per column and dataset.
     - **Uniqueness (25%)**: Duplicate row detection.
     - **Validity (25%)**: Empty/whitespace string detection and suspicious negative business values.
     - **Consistency (20%)**: Statistical IQR (Interquartile Range) outlier detection.
   - Overall Data Quality Score (0.0% – 100.0%) and status classification (**Excellent**, **Good**, **Needs Attention**, **Poor**).
   - Per-column quality status breakdown and structured issue audit (`CRITICAL`, `WARNING`, `INFO`).

4. **Business Intelligence Analytics & Visualizations**
   - Automatic candidate column matching for Revenue, Profit, Quantity, Product, Region, Category, and Date fields.
   - Financial KPIs: Total Revenue, Total Profit, Average Revenue, Average Profit, Total Quantity, Profit Margin.
   - Dynamic Chart.js charts: Revenue by Product (Bar), Revenue by Region (Doughnut), Profit by Product (Bar), Revenue by Category (Bar), and Revenue Trend Over Time (Line).
   - Key Business Highlights: Top Product, Best Region, Top Category, and profitability insights.
   - DQM Quality Warning Banner automatically triggered when Quality Score < 75%.

5. **Data-Grounded AI Assistant (Google Gemini)**
   - Integrated with the modern `google-genai` SDK (`gemini-2.5-flash`).
   - Grounded context builder: Feeds dataset metadata, DQM audit results, and BI analytics to the AI without sending raw dataset dumps.
   - Natural language business question answering with strict hallucination defense ("I don't have enough information in this dataset to answer that").
   - Executive business summary and bulleted recommendations generation.
   - Graceful fallback mode if `GEMINI_API_KEY` is not configured.

6. **Advanced Quality Monitoring & Degradation Alerts**
   - Historical quality snapshot persistence via the database-backed `QualityAudit` table.
   - Tracks quality score change ($\Delta \text{score}$) between dataset inspections.
   - Triggers **🚨 DATA QUALITY DEGRADATION DETECTED** alert if quality score drops by 10 points or more.
   - Centralized threshold configuration for critical missing values, duplicates, and outliers.

7. **Enterprise Security & Rate Limiting**
   - Strict dataset ownership isolation (`Dataset.query.filter_by(id=dataset_id, user_id=current_user.id).first_or_404()`) across all endpoints.
   - Werkzeug password hashing (`scrypt`).
   - Role-separated administrator/client sign-in, CSRF protection, administrator login throttling, and current-password-verified password changes.
   - Login rate limits and temporary account lockout after repeated failed credentials.
   - Admin-issued temporary passwords are stored as hashes, displayed once to the administrator for manual delivery, and require a password change before clients can continue.
   - Administrators can update their business handle and email from profile settings.
   - Password recovery opens a prefilled administrator email draft and never includes or emails an existing password.
   - Security HTTP headers middleware (`X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection`, `Referrer-Policy`).

8. **Business Planning & Reporting**
   - Monthly budgets can be mapped to date, numeric value, and optional group columns in a user's uploaded dataset.
   - Compare numeric measures by business groups and calendar months.
   - Generate printable monthly management reports with budget variances, analysis activity, and data-quality summaries.
   - Search and filter analysis history by text and date, then export account-scoped history as CSV.

---

## 🛠️ Technology Stack

- **Backend**: Python 3.13, Flask 3.1, Flask-SQLAlchemy 3.1, Flask-Migrate 4.1, Flask-Login 0.6, Flask-Limiter 3.8, Flask-WTF
- **Database**: PostgreSQL (Neon Cloud DB) or SQLite, selected through `DATABASE_URL`
- **Data Engineering**: Pandas, NumPy, OpenPyXL
- **AI / LLM Integration**: Google GenAI Python SDK (`google-genai`), Gemini 2.5 Flash Model
- **Frontend**: HTML5, Bootstrap 5.3, Chart.js 4.4, Custom CSS3
- **Production Server**: Gunicorn 23.0

---

## 📐 Application Architecture & Workflow

```text
USER ➔ LOGIN / AUTH ➔ UPLOAD DATASET ➔ DATA PROFILING ➔ DQM ENGINE ➔ QUALITY SCORE ➔ BI ANALYTICS ➔ AI ASSISTANT ➔ MONITORING & ALERTS
```

```text
AI-Business-Intelligence-Assistant/
├── app/
│   ├── models/                  # Users, datasets, budgets, audits, activity
│   ├── routes/                  # Auth, admin, data, analytics, AI, reports
│   ├── services/                # Data, quality, metrics, AI, and auth logic
│   ├── templates/               # Jinja2 pages
│   └── static/                  # CSS, JavaScript, and images
├── docs/PROJECT_OVERVIEW.md     # Full architecture and operations guide
├── migrations/                  # Alembic database migration history
├── tests/                       # Unit and integration test suites
├── uploads/                     # Runtime user dataset files
├── instance/                    # Local instance data, including SQLite
├── config.py                    # Environment-backed configuration
├── app.py                       # Application entry point
├── requirements.txt             # Python dependencies
├── Procfile                     # Production web-process command
└── gunicorn.conf.py             # Gunicorn server settings
```

---

## ⚙️ Installation & Local Setup

### 1. Clone & Navigate to Project
```bash
cd c:\Users\Subhani\Desktop\AI-Business-Intelligence-Assistant
```

### 2. Create & Activate Virtual Environment
```bash
python -m venv venv
# On Windows PowerShell:
.\venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables (`.env`)
Create a `.env` file in the root directory:
```ini
SECRET_KEY=your-production-secret-key-here
DATABASE_URL=postgresql+psycopg://user:password@host/dbname?sslmode=require
GEMINI_API_KEY=your-gemini-api-key-here
ADMIN_USERNAME=@admin
ADMIN_EMAIL=adminaibia@gmail.com
ADMIN_PASSWORD=A12345678
SESSION_COOKIE_SECURE=false
```

The first request after database migrations creates the initial administrator if no administrator account exists. Local development defaults are `@admin` / `A12345678`; the password is hashed and is not reset when the app restarts. Administrators can update their business handle and email in profile settings. Never use the development password in production. Public registration always assigns the `user` role and rejects the reserved administrator username.

### Administrator and production configuration

The administrator signs in at `/admin/login` with the administrator username or email and password; no authenticator code is required. Login attempts are rate-limited, and five failed attempts trigger a 15-minute account lock.

For Render, configure a unique `ADMIN_PASSWORD` of at least 12 characters, `SECRET_KEY`, and a reachable `ADMIN_EMAIL` in the service environment before deploying; retain the existing Neon `DATABASE_URL` and set `SESSION_COOKIE_SECURE=true`. The application refuses to start in production mode when the development admin password, a missing secret key, or insecure session cookies are detected. Do not change the existing `Procfile` or database URL.

SQLAlchemy validates pooled PostgreSQL connections before reuse and recycles them every five minutes to reduce failures from stale Neon connections.

Apply migrations before the first application request after deployment:

```bash
python -m flask --app app db upgrade
```

The role migration adds usernames, roles, active-state flags, and an activity-log table. The temporary-password migrations add a `must_change_password` flag and nullable expiry/first-use timestamps; existing accounts default to no forced password change. The business-reporting migration adds monthly budgets and failed-login lockout fields. Its legacy MFA columns remain in the database migration history but are no longer used by the application. Existing accounts and password hashes are retained. The default administrator is provisioned on the first request after the migration, and existing administrator credentials are never overwritten.

Admins can issue a temporary password from the dashboard by entering only the client's registered email; the app looks up an existing active client account. After verifying the request, the administrator can issue a securely generated password, displayed once for manual delivery to that registered email. It is stored only as a hash, expires after 24 hours, allows one successful login, and requires a password change before the client can continue.

The login page's **Forgot Password?** link opens a prefilled email draft to the administrator. The client reviews the business name, email, and username details and sends the request from their own email application. Password recovery does not email an existing password or use an OTP/passcode flow.

### 5. Apply Database Migrations
```bash
python -m flask --app app db upgrade
```

### 6. Run the Application Locally
```bash
python app.py
```
Open **[http://127.0.0.1:5000](http://127.0.0.1:5000)** in your browser.

---

## 🧪 Automated Testing

To run the complete automated test suite (Phases 1 through 6):

```bash
python -m unittest tests/test_phase1.py tests/test_phase2.py tests/test_phase3.py tests/test_phase4.py tests/test_phase5.py tests/test_phase6.py
```

Include role/authentication and business-report coverage with:

```bash
python -m unittest tests.test_role_auth tests.test_business_reports
```

For a clean local test database, set `DATABASE_URL` to a temporary SQLite database, run `python -m flask --app app db upgrade`, then run the test commands. Avoid running tests against a production Neon URL.

---

## 🚢 Production Deployment

To start the server in production mode using Gunicorn:

```bash
gunicorn --config gunicorn.conf.py app:app
```

---

## 🔒 Security Audit Checklist

- [x] **No Hardcoded Credentials**: Secrets (`SECRET_KEY`, `DATABASE_URL`, `GEMINI_API_KEY`) loaded strictly from environment variables.
- [x] **Dataset Ownership Isolation**: Enforced on all routes (`view`, `preview`, `quality`, `analytics`, `ai`, `delete`).
- [x] **File Upload Protection**: Extension whitelist, UUID filenames, 50MB size limit, content validation.
- [x] **SQL Injection Prevention**: Safe SQLAlchemy ORM queries with parameterized binding.
- [x] **XSS Protection**: Jinja2 auto-escaping & Security HTTP headers.
- [x] **Rate Limiting**: Configured via `Flask-Limiter` to prevent brute force and API abuse.
- [x] **Production Error Handling**: Custom 404 and 500 pages without stack trace leakage.
