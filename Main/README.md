# Financial Intelligence Platform

This project provides a suite of backend services for financial analysis, reporting, and chat interaction, incorporating Large Language Models (LLMs), Retrieval-Augmented Generation (RAG), real-time data fetching, and MLOps practices.

---

## 1. Top-Level Layout

```
Main/
├── .github/
│   └── workflows/
│       └── ci.yml            # GitHub Actions CI/CD workflow
├── backend/
│   ├── chat_server/          # Django project – global settings & routing for chat app
│   ├── chat_server_app/      # Django app – main chat application logic & APIs
│   ├── datascraper/          # Utilities for RAG, document embedding, and web scraping
│   ├── data_providers/       # Module for fetching real-time external data (news, FX)
│   ├── financial_reports_fastapi/ # FastAPI service for generating financial reports
│   │   └── Dockerfile.fastapi  # Dockerfile for the FastAPI service
│   ├── chart_generator/      # Module for generating charts
│   ├── Dockerfile.django     # Dockerfile for the Django application
│   ├── .dockerignore         # Specifies files to ignore in Docker builds
│   ├── requirements.txt      # Consolidated Python dependencies for Django app
│   ├── manage.py             # Django CLI helper
│   └── static/               # Shared static files (e.g., generated charts)
├── frontend/                 # Browser extension (Webpack-bundled JS) - Structure as before
│   ├── ...
└── Requirements/             # Original pinned Python dependencies (pip) - Review if still primary
```

---

## 2. Backend Services (`backend/`)

The backend consists of two main services: a Django application for chat functionalities and a FastAPI application for financial report generation.

### 2.1 Django Chat Service

#### 2.1.1 `chat_server/` – Django Project Scaffolding
*   Standard Django project setup (`settings.py`, `urls.py`, `wsgi.py`). `settings.py` includes configuration for installed apps, CORS, etc. `urls.py` is the global URL dispatcher for the Django service.

#### 2.1.2 `chat_server_app/` – Primary Django Application
*   **`views.py`**: Handles chat interactions, including:
    *   General chat using LLMs.
    *   Queries to the Retrieval-Augmented Generation (RAG) system.
    *   Direct fetching of real-time financial news and FX rates using `data_providers`.
    *   Management of preferred URLs and document uploads for the RAG knowledge base.
    *   Interaction logging.
*   **`models.py`, `admin.py`, `apps.py`**: Conventional Django components.
*   **`tests.py`**: Unit tests for the application views.
*   **Runtime Artefacts (git-ignored):** `questionLog.csv`, `preferred_urls.txt`, `*.pkl` (embedding indices from `datascraper`).

#### 2.1.3 `datascraper/` – RAG and Embedding Utilities
*   **`cdm_rag.py`**: Orchestrates the RAG pipeline for querying indexed documents.
    *   *Note on Local Embeddings:* While `create_embeddings.py` (below) uses local models to *create* document embeddings, modifications to `cdm_rag.py` to use local embeddings for the *querying* part were blocked by tool limitations. Thus, querying via `cdm_rag.py` might still use its original OpenAI-based embedding method for questions.
*   **`create_embeddings.py`**: Handles batch embedding of uploaded documents using local Sentence Transformer models (e.g., `all-MiniLM-L6-v2`) and creates/updates a FAISS index.
*   **`datascraper.py`**: Contains general helper functions for web scraping and interacting with LLM APIs (used by `chat_server_app`).
*   **`requirements.txt`**: Python dependencies specific to `datascraper` utilities (now part of the main `backend/requirements.txt`).

#### 2.1.4 `data_providers/` – Real-time Data Fetching
*   **`news_and_fx.py`**:
    *   `fetch_financial_news()`: Fetches recent financial news using the NewsAPI.
    *   `fetch_fx_exchange_rates()`: Fetches current FX rates using `api.exchangerate.host`.
*   **`tests/test_news_and_fx.py`**: Unit tests for this module.

### 2.2 FastAPI Financial Reports Service

#### 2.2.1 `financial_reports_fastapi/` – FastAPI Application
*   **Purpose**: Provides an API for on-demand generation of hourly financial reports.
*   **`main.py`**: Defines FastAPI app instance, endpoints (`/`, `/health`, `/reports/hourly/`), and static file serving configuration for charts.
    *   The `/reports/hourly/` endpoint triggers the report generation.
*   **`report_generator.py`**: Contains the core logic for report generation using a LangChain agent (`gpt-4o` based). This agent utilizes a suite of tools:
    *   Real-time news fetching (via `data_providers.news_and_fx`).
    *   Real-time FX rate fetching (via `data_providers.news_and_fx`).
    *   RAG search for querying general documents (via `datascraper.cdm_rag`).
    *   Chart generation (via `chart_generator.charting`).
    *   Integrates with Weights & Biases for metrics logging.
*   **`requirements.txt`**: Python dependencies for this service (FastAPI, Uvicorn, LangChain, OpenAI, W&B, Matplotlib).
*   **`Dockerfile.fastapi`**: Dockerfile for containerizing this service.
*   **`tests/`**: Unit tests for `main.py` and `report_generator.py`.

#### 2.2.2 `chart_generator/` – Charting Utilities
*   **`charting.py`**: Uses Matplotlib to generate charts (e.g., line charts from numerical data). Charts are saved as images.
*   **`tests/test_charting.py`**: Unit tests for this module.

### 2.3 Shared `static/` Directory
*   Located at `Main/backend/static/`.
*   Used to store static assets, notably generated charts from `chart_generator` which are then served by the FastAPI service.

---

## 3. MLOps Practices

### 3.1 Containerization (Docker)
*   **Django Service:** `Main/backend/Dockerfile.django` builds the image for the Django chat application.
*   **FastAPI Service:** `Main/backend/financial_reports_fastapi/Dockerfile.fastapi` builds the image for the financial reports service.
*   **Build Context:** For `Dockerfile.fastapi`, the Docker build context should be `Main/backend/` to allow copying shared modules like `chart_generator` and `data_providers`.
    *   Example Django build: `docker build -f Dockerfile.django -t django_chat_service .` (from `Main/backend/`)
    *   Example FastAPI build: `docker build -f financial_reports_fastapi/Dockerfile.fastapi -t fastapi_report_service .` (from `Main/backend/`)
*   A `.dockerignore` file in `Main/backend/` helps keep image sizes minimal.
*   (Future work could include a `docker-compose.yml` for easier multi-container management).

### 3.2 CI/CD (GitHub Actions)
*   The workflow is defined in `Main/.github/workflows/ci.yml`.
*   **Triggers**: On push or pull request to `main` and `develop` branches.
*   **Jobs**:
    1.  **Linting**: Uses Flake8 to check Python code quality in `Main/backend/`.
    2.  **Unit Testing**: Runs unit tests for `data_providers`, `chart_generator`, `financial_reports_fastapi`, and `chat_server_app`.
    3.  **Docker Builds**: Builds Docker images for both Django and FastAPI services to validate Dockerfile setup.

### 3.3 Metrics Logging (Weights & Biases)
*   The FastAPI service (`report_generator.py`) is integrated with Weights & Biases (`wandb`).
*   It logs metrics related to financial report generation, such as:
    *   Generation duration.
    *   Report length.
    *   Success/failure status and error messages.
    *   Input query used.
*   This requires the `WANDB_API_KEY` environment variable to be set.

---

## 4. Environment Variables

The following environment variables are required for full functionality:

*   `OPENAI_API_KEY`: For accessing OpenAI models (used by LangChain agent in FastAPI and potentially by `cdm_rag.py`).
*   `NEWSAPI_KEY`: For fetching news articles via NewsAPI (used by `data_providers.news_and_fx`).
*   `WANDB_API_KEY`: For logging metrics to Weights & Biases (used by the FastAPI service).
*   `API_KEY7`: (Review if still used) An older OpenAI API key variable, potentially still used in parts of `datascraper` or `cdm_rag.py`. It's recommended to consolidate API key usage.
*   `DJANGO_SETTINGS_MODULE`: Should be set to `chat_server.settings` for running Django management commands or tests outside of `manage.py` context (e.g., in some CI steps).

It's recommended to use a `.env` file in the `Main/backend/` directory to manage these variables locally. `python-dotenv` is included in requirements.

---

## 5. Running the Project

### 5.1 Using Docker (Recommended for Services)

1.  **Build the Images:**
    *   Navigate to `Main/backend/`.
    *   Build Django service: `docker build -f Dockerfile.django -t django_chat_service .`
    *   Build FastAPI service: `docker build -f financial_reports_fastapi/Dockerfile.fastapi -t fastapi_report_service .`

2.  **Run the Containers:**
    *   **Django Service:**
        ```bash
        docker run -d -p 8000:8000 \
               -e OPENAI_API_KEY="your_openai_key" \
               -e NEWSAPI_KEY="your_newsapi_key" \
               # Add other necessary env vars for Django (e.g., API_KEY7 if needed)
               --name chat_service django_chat_service
        ```
    *   **FastAPI Service:**
        ```bash
        docker run -d -p 8001:8001 \
               -e OPENAI_API_KEY="your_openai_key" \
               -e NEWSAPI_KEY="your_newsapi_key" \
               -e WANDB_API_KEY="your_wandb_key" \
               # Add other necessary env vars for FastAPI
               --name report_service fastapi_report_service
        ```
    *   Ensure the `Main/backend/static` directory is properly handled or mounted if charts need to persist across container restarts or be shared. For development, the current Dockerfiles copy it in.

### 5.2 Local Development (Without Docker)

1.  **Setup Environment:** Create a virtual environment and install dependencies:
    *   Django: `pip install -r Main/backend/requirements.txt`
    *   FastAPI: `pip install -r Main/backend/financial_reports_fastapi/requirements.txt`
2.  **Set Environment Variables:** Export the variables listed above.
3.  **Run Django App:**
    *   Navigate to `Main/backend/`.
    *   Run migrations: `python manage.py migrate`
    *   Run server: `python manage.py runserver` (usually on port 8000)
4.  **Run FastAPI App:**
    *   Navigate to `Main/backend/financial_reports_fastapi/`.
    *   Run server: `uvicorn main:app --host 0.0.0.0 --port 8001 --reload`

---

## 6. Running Tests

*   Navigate to `Main/backend/`.
*   **Django Tests:** `python manage.py test chat_server_app`
*   **Other Unit Tests** (from `Main/backend/` directory):
    *   `python -m unittest discover -s data_providers/tests -p 'test_*.py'`
    *   `python -m unittest discover -s chart_generator/tests -p 'test_*.py'`
    *   `python -m unittest discover -s financial_reports_fastapi/tests -p 'test_*.py'`
*   Tests are also run automatically via the GitHub Actions CI workflow.

---

## 7. Front-End
(Original Front-End section can be kept as is, assuming no changes were requested for it.)

Front-end's file structure:
```markdown
frontend/
├── dist/           # Compiled bundle – served by extension (DO NOT EDIT)
└── src/
├── main.js     # Extension bootstrapper
├── manifest.json  # Required Web-Extension manifest (permissions, icons…)
├── modules/    # Feature-specific JS (each with optional *.css)
├── styles/     # Shared CSS (BEM / Tailwind utilities)
└── textbox.css # LEGACY – kept only for historical reference
```
Webpack information:

| Tooling             | Notes                                          |
|---------------------|------------------------------------------------|
| **Webpack**         | Bundles ES modules, targets modern browsers    |
| **Babel**           | Transpiles experimental JS → ES2018            |
| `webpack.config.js` | Two entry points: background & content scripts |

---
```
