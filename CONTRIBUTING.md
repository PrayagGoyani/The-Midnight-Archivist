# Contributing to The Midnight Archivist

Thank you for your interest in contributing to **The Midnight Archivist**. We welcome contributions from developers, writers, and digital archivists.

This guide outlines our development workflow, standards, and pull request process to ensure that all contributions preserve our local-first, privacy-respecting architectural principles and editorial design aesthetic.

---

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Development Environment Setup](#development-environment-setup)
3. [Repository Structure](#repository-structure)
4. [Branching and Commit Conventions](#branching-and-commit-conventions)
5. [Code Style & Standards](#code-style--standards)
6. [Testing & Verification](#testing--verification)
7. [Submitting a Pull Request](#submitting-a-pull-request)
8. [Reporting Issues](#reporting-issues)

---

## 1. Prerequisites

Before setting up the project, ensure you have the following installed on your workstation:

- **Python:** 3.10 or 3.11 (Python 3.11 recommended).
- **Node.js:** 18 LTS or 20 LTS (with `npm`).
- **Ollama:** Installed locally from [https://ollama.com](https://ollama.com).
  - Generative model: `llama3.2:3b` (`ollama pull llama3.2:3b`)
  - Embedding model: `nomic-embed-text` (`ollama pull nomic-embed-text`)
- **Git:** Version 2.30 or higher.
- **Chrome / Chromium:** Required for Playwright browser acceptance tests.

---

## 2. Development Environment Setup

The application is structured as a decoupled full-stack architecture with a FastAPI backend and a React/Vite frontend.

### A. Clone and Configure

```powershell
git clone https://github.com/<your-username>/midnight-archivist.git
cd midnight-archivist

# Copy environment configuration
Copy-Item backend\.env.example backend\.env
Copy-Item frontend\.env.example frontend\.env
```

### B. Backend Setup (Windows PowerShell)

```powershell
cd backend

# Create virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Start local Ollama daemon (in a separate terminal)
ollama serve

# Start the FastAPI development server
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Interactive API documentation will be available at: [http://127.0.0.1:8000/api/docs](http://127.0.0.1:8000/api/docs)

### C. Frontend Setup (Windows PowerShell)

```powershell
cd ..\frontend

# Install node dependencies
npm install

# Start Vite dev server
npm run dev
```

The user interface will be accessible at: [http://localhost:5173](http://localhost:5173)

---

## 3. Repository Structure

```text
midnight-archivist/
├── backend/
│   ├── app/
│   │   ├── main.py              # Application entry point & router mounting
│   │   ├── config.py            # Pydantic Settings & environment parsing
│   │   ├── database.py          # SQLAlchemy SQLite connection with WAL mode
│   │   ├── models.py            # ORM Models (Document, Chunk, Story)
│   │   ├── schemas.py           # Pydantic request/response schemas
│   │   ├── routers/             # API routes (documents, search, stories, health)
│   │   └── services/            # Ingestion, chunking, Ollama clients, story engine
│   ├── tests/                   # 151 comprehensive unit and integration tests
│   └── requirements.txt         # Pinned backend dependencies
├── frontend/
│   ├── src/
│   │   ├── components/          # Design system components (Button, Modal, Badges)
│   │   ├── pages/               # Archive, Writing Desk, Reading Room, Shelf, Settings
│   │   ├── services/            # Typed API client wrappers
│   │   ├── styles/              # Design tokens and editorial CSS
│   │   └── types/               # TypeScript domain interfaces
│   ├── package.json             # Pinned frontend dependencies
│   ├── tsconfig.json            # Strict TypeScript configuration
│   └── vite.config.ts           # Vite build & reverse-proxy configuration
├── screenshots/
│   └── final/                   # High-fidelity release demonstration images
├── .env.example                 # Root configuration template
├── .gitignore                   # Strict exclusions for databases, weights & uploads
├── CONTRIBUTING.md               # Contribution guidelines
└── README.md                    # Primary repository documentation
```

---

## 4. Branching and Commit Conventions

### Branch Naming
- Features: `feature/short-description` (e.g., `feature/epub-parser`)
- Bug Fixes: `fix/short-description` (e.g., `fix/chunk-overlap-boundary`)
- Documentation: `docs/short-description` (e.g., `docs/troubleshooting-guide`)
- Refactoring: `refactor/short-description` (e.g., `refactor/sqlite-connection-pool`)

### Commit Messages
We follow the **Conventional Commits** specification:

```text
<type>(<scope>): <short imperative description>

[optional body explaining motivation and context]

[optional footer(s) referencing issue numbers]
```

**Allowed Types:**
- `feat`: A new user-facing capability or API endpoint.
- `fix`: A bug fix or boundary correction.
- `docs`: Documentation updates only.
- `style`: Formatting, missing semicolons, CSS refinements.
- `refactor`: Code restructuring without behavioral changes.
- `test`: Adding or updating tests.
- `chore`: Dependency bumps, build script changes.

---

## 5. Code Style & Standards

### Backend (Python)
- Follow **PEP 8** formatting and conventions.
- Explicit type annotations on all function signatures (`typing` / `from __future__ import annotations`).
- Pydantic models for all API request payloads and responses.
- SQLAlchemy 2.0 style queries.
- Never write credentials, raw disk paths, or user data into log output.

### Frontend (TypeScript & React)
- Strict mode TypeScript enabled (`noImplicitAny`, `strictNullChecks`).
- Functional React components with hooks.
- Adhere to the established **editorial design system tokens** in `frontend/src/styles/variables.css`:
  - Background: `#F4F0E7`
  - Surface: `#FBF9F4`
  - Primary Ink: `#25231F`
  - Secondary Slate: `#746F64`
  - Border Rule: `#D8D0C2`
  - Accents: Deep Wine (`#6F3F3B`) and Muted Sage (`#66705A`)
  - Typography: Merriweather (serif headings/narrative), Inter (UI), IBM Plex Mono (telemetry).
- No floating neon glow effects, artificial glassmorphism, or fake indeterminate spinners.

---

## 6. Testing & Verification

Every pull request must pass the full test suite and build pipeline before merge approval.

### Run Backend Pytest Suite
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pytest -v
```
All 151 tests run fully offline using mocked Ollama HTTP responses.

### Run Frontend TypeScript Check & Build
```powershell
cd frontend
npx tsc --noEmit
npm run build
```

### Run End-to-End Browser Acceptance Suite (Optional, requires local Ollama)
```powershell
cd frontend
node capture_final_screenshots.cjs
```

---

## 7. Submitting a Pull Request

1. Fork the repository and create your feature branch from `master` (or `main`).
2. Implement your changes following the code style guidelines.
3. Ensure all existing automated tests pass and add unit tests for new behavior.
4. Verify repository hygiene:
   - **DO NOT** commit SQLite database files (`.db`, `.db-wal`, `.db-shm`).
   - **DO NOT** commit personal `.env` files or API keys.
   - **DO NOT** commit uploaded documents in `backend/data/uploads/`.
5. Open a Pull Request on GitHub with a clear summary:
   - **What:** Brief summary of changes.
   - **Why:** The problem or improvement addressed.
   - **Verification:** Automated tests or manual steps performed.

---

## 8. Reporting Issues

If you encounter a bug or unexpected behavior:
1. Check the existing GitHub Issues to see if the issue has already been reported.
2. Open a new issue with:
   - Operating system and version.
   - Python and Node.js versions.
   - Ollama version and installed models (`ollama list`).
   - Clear step-by-step reproduction instructions.
   - Relevant log output (with personal secrets and private documents redacted).
