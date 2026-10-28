# Employee Learning Path Advisory Agent

**MVP Implementation v1.0** built strictly following [`Employee_Learning_Path_Advisory_Agent_Documentation.md`](./Employee_Learning_Path_Advisory_Agent_Documentation.md).

---

## 1. Overview & Capabilities

The **Employee Learning Path Advisory Agent** is an enterprise learning-management assistant that deterministically calculates skill gaps, sequences prerequisites using Kahn's topological sort, verifies corporate budget and study time constraints, tracks lesson completion and rubric assessments, and provides course-aware AI doubt solving backed by Google Gemini.

### Core Functional Capabilities:
- **FR-01 Employee Skills & Profiles**: Stores self-assessed vs rubric-verified skills on a 0–5 proficiency scale.
- **FR-02 Skill-Gap Analysis**: Deterministically evaluates $\text{gap}(s) = \max(0, \text{target} - \text{current})$, excludes 0-gap skills, and flags unfulfillable competencies.
- **FR-03 Course Matching & Approved Catalogue**: Recommends only approved catalogue-backed courses without fabricating course offerings.
- **FR-04 Prerequisite Graph & Kahn's DAG**: Directed acyclic graph sequencing, cycle detection (`CycleDetectedException`), and recursive auto-insertion of missing prerequisite foundations (`is_foundation: True`).
- **FR-05 Plan Constraints**: Enforces $0 zero-budget rules, annual budget caps ($500 standard), and dynamically flags $\le 3\text{ hrs/week}$ as *Extended-Timeline Plans*.
- **FR-06 Progress Tracking**: Idempotent lesson completion tracking without duplications.
- **FR-07 Rubric Proficiency Updates**: Completing lessons alone does not falsely certify mastery; verified proficiency is elevated exclusively through rubric-graded assessments.
- **FR-08 Course-Aware AI Chatbot**: Google Gemini LLM bridge grounded in course context with hints before answers and BM25 RAG evidence citations from corporate policy documents (`learning_policy.pdf`).
- **FR-09 Versioned Roadmap Updates**: Recalculates plans upon constraint or proficiency changes and increments version without erasing historical records.
- **FR-10 Responsible AI Guardrails**: Strict server-side disclaimers never guaranteeing promotions, salary increases, or certifications.

---

## 2. Project Architecture

```text
2/
├── backend/
│   ├── app/
│   │   ├── agent/
│   │   │   ├── engine.py          # Deterministic DAG Kahn's algorithm & constraints
│   │   │   ├── tools.py           # 13 pure Python planning functions from Section 8
│   │   │   └── gemini_advisor.py  # Course-aware Gemini chatbot + RAG citations & guardrails
│   │   ├── api/
│   │   │   └── routes.py          # REST API endpoints matching Section 11
│   │   ├── core/
│   │   │   ├── config.py          # Configuration & settings
│   │   │   └── database.py        # MongoDB client connection & fallback
│   │   ├── models/
│   │   │   └── schemas.py         # Pydantic schemas matching Section 9 MongoDB models
│   │   ├── repositories/
│   │   │   └── mongo_repository.py# Repository pattern (MongoDB + local JSON fallback)
│   │   ├── services/
│   │   │   ├── ingestion.py       # Multi-format ingestion (CSV, XLSX, PDF, JSON)
│   │   │   └── policy_rag.py      # Self-contained BM25 policy retrieval & citations
│   │   └── main.py                # FastAPI ASGI entry point
│   ├── tests/
│   │   ├── conftest.py            # Test fixtures and automatic ingestion setup
│   │   ├── test_engine.py         # Tests for DAG, gaps, constraints, idempotency, validation
│   │   ├── test_assessment.py     # Tests for rubric-verified proficiency elevation
│   │   ├── test_chat.py           # Tests for course awareness, citations, isolation, resilience
│   │   └── test_api.py            # End-to-end API integration tests
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── DashboardView.tsx     # 5.1 Dashboard (progress %, hours, active/completed)
│   │   │   ├── ProfileView.tsx       # 5.2 Profile & self-assessment vs verified rating
│   │   │   ├── RoadmapView.tsx       # 5.3 Learning Roadmap (interactive DAG timeline)
│   │   │   ├── CoursePageView.tsx    # 5.4 My Learning / Course Page (lessons & quizzes)
│   │   │   ├── ProgressView.tsx      # 5.5 Skills & Progress (target vs current comparisons)
│   │   │   ├── AIAdvisorView.tsx     # 5.6 AI Learning Assistant (doubt-solving chat)
│   │   │   └── AdminCatalogView.tsx  # 5.7 Minimal Admin / Catalogue management
│   │   ├── lib/
│   │   │   └── api.ts                # Typed client API service
│   │   ├── App.tsx                   # Main navigation shell with employee switcher
│   │   └── main.tsx
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── index.html
├── data/
│   ├── courses.csv                  # Course catalogue
│   ├── employee_skills.csv          # Base employee skill assessments
│   ├── competency_matrix.xlsx       # Target role competency matrices
│   ├── learning_policy.pdf          # Corporate policy document
│   ├── lessons_and_quizzes.json     # Modular lessons, quizzes, and rubrics
│   └── storage_cache.json           # Local persistent JSON repository
├── scripts/
│   └── import_data.py               # Data ingestion runner script
├── Employee_Learning_Path_Advisory_Agent_Documentation.md
├── .gitignore
└── README.md
```

---

## 3. Quick Start Guide

### Step 1: Install Backend Dependencies & Ingest Data
```bash
# In project root
python -m pip install -r backend/requirements.txt

# Run initial ingestion
python scripts/import_data.py
```

### Step 2: Start the FastAPI Backend
```bash
# Launch FastAPI development server
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```
The REST API will be available at `http://127.0.0.1:8000`. Interactive Swagger documentation is at `http://127.0.0.1:8000/docs`.

### Step 3: Start the React Frontend
```bash
# Navigate to frontend and launch Vite dev server
cd frontend
npm run dev
```
Open `http://localhost:5173` in your browser.

---

## 4. Automated Testing Suite

All 15 verification checklist criteria from Section 15 of `Employee_Learning_Path_Advisory_Agent_Documentation.md` are tested with pytest:

```bash
# Run the complete test suite
python -m pytest backend/tests -v
```

### Verification Checklist Coverage:
1. `test_checklist_1_foundation_recommendation`: Employee with no prior skill receives foundation-level recommendation.
2. `test_checklist_2_missing_prerequisite_added_before_advanced`: Missing prerequisite is added before an advanced course.
3. `test_checklist_3_catalogue_integrity`: A course absent from the catalogue is not invented.
4. `test_checklist_4_zero_budget_constraint`: Zero budget only permits courses whose recorded cost is zero.
5. `test_checklist_5_extended_timeline_hours`: Limited weekly study hours produce a longer plan with extended timeline flag.
6. `test_checklist_6_plan_revision_preserves_history`: Increasing weekly hours updates the plan and preserves history.
7. `test_checklist_7_idempotent_progress_update`: Completing a lesson updates progress exactly once.
8. `test_checklist_8_lesson_completion_does_not_falsely_certify_mastery`: A lesson completion alone does not falsely certify mastery; passing a rubric assessment elevates verified level.
9. `test_checklist_9_chatbot_context_awareness`: Chatbot uses the current course and proficiency context.
10. `test_checklist_10_employee_data_isolation`: Chatbot and records do not expose another employee's information.
11. `test_checklist_11_rag_citations_distinguished`: Policy questions cite approved documents and distinguish general explanations.
12. `test_checklist_12_missing_content_acknowledged`: Missing course material or policy evidence is acknowledged instead of fabricated.
13. `test_checklist_13_api_key_isolation`: API key is not present in frontend files and safely isolated in backend environment.
14. `test_checklist_14_schema_validation_rejections`: Invalid scores, durations, and proficiency levels are rejected by schema.
15. `test_checklist_15_resilience_on_llm_failure`: A simulated failed LLM request returns a useful answer without corrupting learning records.

---

## 5. Multi-LLM Provider Fallback System

The Advisory Agent features a resilient multi-provider LLM abstraction supporting **Google Gemini**, **OpenAI**, and **xAI Grok** with automatic silent failover.

### Provider Architecture
```text
Learner Question / Doubt Resolution
         │
         ▼
┌──────────────────────────────────────────────┐
│             LLMFallbackManager               │
│  - Reads LLM_PRIMARY_PROVIDER & FALLBACK_ORDER│
│  - Bounded retries for transient errors       │
│  - Immediate fallback on permanent errors     │
│  - Preserves RAG context & conversation turns │
│  - Observability & redaction of secrets       │
└──────────────────────┬───────────────────────┘
                       │
       ┌───────────────┼───────────────┐
       ▼               ▼               ▼
┌──────────────┐┌──────────────┐┌──────────────┐
│GeminiProvider││OpenAIProvider││ GrokProvider │
│(Multi-Key Rot)│(gpt-4o-mini) │(grok-3-mini)  │
└──────────────┘└──────────────┘└──────────────┘
```

### Environment Configuration

Configure providers in `backend/.env` (or through system environment variables):

```env
# Primary provider
LLM_PRIMARY_PROVIDER=gemini

# Fallback priority order
LLM_FALLBACK_ORDER=gemini,openai,grok

# Google Gemini (Primary)
# Supports single key or comma-separated multiple keys for safe internal rotation
GEMINI_API_KEYS=your_gemini_api_key
GEMINI_MODEL=gemini-2.0-flash

# OpenAI (Backup 1)
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o-mini

# xAI Grok (Backup 2)
XAI_API_KEY=your_xai_api_key
XAI_MODEL=grok-3-mini

# Optional request timeout in seconds
LLM_REQUEST_TIMEOUT=30
```

### Automatic Fallback Behavior
1. **Primary First**: Requests always attempt the primary provider first (`LLM_PRIMARY_PROVIDER`).
2. **Key Rotation on Gemini**: If multiple Gemini keys are configured in `GEMINI_API_KEYS`, a 429 quota exhaustion automatically rotates to the next key before switching providers.
3. **Transient vs. Permanent Errors**:
   - **Transient (429 Rate Limits, Network Timeouts, 5xx Server Errors)**: Retries with exponential backoff before failing over to the next provider.
   - **Permanent (Invalid API Keys, 401/403 Unauthorized, 404 Model Unavailable)**: Fails over immediately to the next provider without wasteful retries.
4. **Context Preservation**: Course metadata, retrieved Chroma lesson chunks, policy evidence, learner proficiency, and conversational turns are preserved identically across all providers.
5. **Observability & Status Endpoint**: Inspect safe provider health and recent executions via `GET /api/llm/status` (zero credentials or sensitive tokens exposed).
