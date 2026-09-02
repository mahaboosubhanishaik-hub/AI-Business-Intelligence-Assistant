# AI Business Intelligence Assistant

An enterprise-grade, data-grounded Business Intelligence (BI) platform combining automated dataset management, data profiling, Data Quality Monitoring (DQM), financial business analytics, interactive Chart.js visualizations, and an AI Business Intelligence Assistant powered by Google Gemini.

---

## 🚀 Purpose

The **AI Business Intelligence Assistant** enables business users and decision-makers to effortlessly upload datasets (CSV or Excel), evaluate dataset health, inspect financial KPIs, visualize multi-dimensional performance metrics, track data quality degradation over time, and interact with an AI assistant for data-grounded insights and executive recommendations.

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
   - Historical quality snapshot persistence via `QualityAudit` PostgreSQL table.
   - Tracks quality score change ($\Delta \text{score}$) between dataset inspections.
   - Triggers **🚨 DATA QUALITY DEGRADATION DETECTED** alert if quality score drops by 10 points or more.
   - Centralized threshold configuration for critical missing values, duplicates, and outliers.

7. **Enterprise Security & Rate Limiting**
   - Strict dataset ownership isolation (`Dataset.query.filter_by(id=dataset_id, user_id=current_user.id).first_or_404()`) across all endpoints.
   - Werkzeug password hashing (`scrypt`).
   - Rate limiting via `Flask-Limiter`.
   - Security HTTP headers middleware (`X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection`, `Referrer-Policy`).

---

## 🛠️ Technology Stack

- **Backend**: Python 3.13, Flask 3.1, Flask-SQLAlchemy 3.1, Flask-Migrate 4.1, Flask-Login 0.6, Flask-Limiter 3.8
- **Database**: PostgreSQL (Neon Cloud DB) / SQLite fallback
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
│   ├── models/
│   │   ├── user.py              # User authentication model
│   │   ├── dataset.py           # Dataset metadata model
│   │   └── quality_audit.py     # Quality audit snapshot model
│   ├── routes/
│   │   ├── __init__.py          # Main landing & dashboard routes
│   │   ├── auth.py              # Auth routes (Login, Register, Logout)
│   │   ├── data.py              # Dataset upload, preview, DQM routes
│   │   ├── analytics.py         # BI Analytics dashboard routes
│   │   └── ai.py                # AI Assistant chatbot routes
│   ├── services/
│   │   ├── data_loader.py       # Dataset ingestion & validation
│   │   ├── data_profiler.py     # In-depth dataset profiling engine
│   │   ├── data_quality.py      # DQM 4-dimension scoring engine
│   │   ├── analytics.py         # Financial BI aggregation & charts
│   │   ├── ai_service.py        # Gemini AI context & Q&A service
│   │   └── monitoring.py        # Quality tracking & degradation alerts
│   ├── templates/               # Bootstrap 5 Jinja2 HTML templates
│   └── static/                  # Static assets
├── migrations/                  # Alembic database migration scripts
├── tests/                       # Automated test suites (Phases 1-6)
├── config.py                    # Environment configuration loader
├── Procfile                     # Production Gunicorn startup configuration
├── gunicorn.conf.py             # Gunicorn worker & socket settings
├── app.py                       # Main application entry point
├── requirements.txt             # Python dependencies
└── README.md                    # System documentation
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
```

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
