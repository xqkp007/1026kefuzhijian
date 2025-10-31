# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an **Agent Stability Evaluation Tool** - a full-stack application for testing and measuring the consistency of AI agent outputs. The system allows users to upload test datasets, configure agent endpoints, run automated evaluations (5 calls per question), and export detailed results.

**Tech Stack:**
- Backend: FastAPI + Celery + PostgreSQL + Redis
- Frontend: React 18 + TypeScript + Vite + Ant Design 5
- Language: Python 3.11 (backend), TypeScript 5 (frontend)

## Development Commands

### Quick Start (All Services)
```bash
./start_all.sh
```
This starts FastAPI (port 8000), Celery worker, and Vite dev server (port 5173).

### Backend

**Setup:**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env  # Edit .env with your config
alembic upgrade head
```

**Run Services:**
```bash
# FastAPI server
uvicorn app.main:app --reload --port 8000

# Celery worker
celery -A app.celery_app worker --loglevel=info -Q evaluation

# Or use convenience scripts
./backend/start_services.sh  # Start all backend services
./backend/stop_services.sh   # Stop all backend services
```

**Testing:**
```bash
pytest                    # Run all tests
pytest --cov=app          # With coverage
pytest tests/test_foo.py  # Single test file
```

**Code Quality:**
```bash
ruff check .    # Linting
mypy app        # Type checking
```

### Frontend

**Setup:**
```bash
cd frontend
npm install
```

**Development:**
```bash
npm run dev      # Dev server on http://localhost:5173
npm run build    # Production build
npm run preview  # Preview production build
npm run lint     # ESLint
```

**Mock Service Worker (MSW):**
- MSW is enabled in development for API mocking
- Mock handlers are in `frontend/src/mocks/`
- Control via `VITE_ENABLE_MSW` environment variable

## Architecture

### Backend Structure

```
backend/app/
├── api/routes/        # FastAPI route handlers
├── core/              # Settings, config, logging
├── db/
│   ├── models/        # SQLAlchemy ORM models
│   └── repositories/  # Data access layer
├── schemas/           # Pydantic request/response schemas
├── services/          # Business logic + Celery tasks
├── utils/             # Helper functions
├── examples/          # SDK usage examples (e.g., Zhipu API)
└── prompts/zhipu/     # Prompt templates for Zhipu integration
```

**Key Files:**
- `app/main.py`: FastAPI application entry point
- `app/celery_app.py`: Celery configuration and task registration
- `backend/alembic/`: Database migration scripts
- `backend/.env`: Environment configuration (copy from `.env.example`)

### Frontend Structure

```
frontend/src/
├── pages/
│   ├── CreateTask/    # Task creation form
│   ├── TaskList/      # Task overview with status
│   └── TaskResults/   # Detailed evaluation results (paginated)
├── components/Layout/ # Shared layout component
├── api/               # Axios API clients
├── types/             # TypeScript type definitions
├── utils/             # Utility functions
├── mocks/             # MSW mock handlers
└── router.tsx         # React Router configuration
```

**Routes:**
- `/` - Create new evaluation task (default page)
- `/tasks` - View all tasks
- `/tasks/:taskId/results` - View task results (requires task to be completed)

### Data Flow

1. User uploads dataset (CSV/Excel with `question` and `standard_answer` columns)
2. Frontend sends task creation request to FastAPI
3. Backend creates task record in PostgreSQL and enqueues Celery job
4. Celery worker calls agent API 5 times per question (configurable via `RUNS_PER_ITEM`)
5. Results stored in PostgreSQL with timing metrics
6. Frontend polls task status and displays results
7. User can export results to CSV

## Key Configuration

### Backend Environment Variables (`.env`)

**Required:**
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection for Celery broker/backend
- `ZHIPU_API_KEY`: Zhipu AI API key (if using Zhipu model)

**Optional:**
- `RUNS_PER_ITEM=5`: Number of API calls per question
- `TIMEOUT_SECONDS=30`: Agent API call timeout
- `EVALUATION_CONCURRENCY=1`: Celery worker concurrency
- `RATE_LIMIT_PER_AGENT=1/s`: Rate limit per agent endpoint
- `MAX_DATASET_ROWS=1000`: Maximum rows in uploaded dataset
- `AGENT_API_ALLOWLIST=*`: Allowed agent API domains (comma-separated)

**Zhipu Model Settings:**
- `ZHIPU_MODEL_ID=glm-4.6`
- `ZHIPU_TEMPERATURE=0.7`
- `ZHIPU_DIALOG_MODE=single` (or `multi` for conversation mode)

### Frontend Environment Variables

Create `.env.local` in `frontend/`:
- `VITE_API_BASE_URL`: Backend API URL (default: http://localhost:8000)
- `VITE_ENABLE_MSW`: Enable MSW mocking (true/false)

## Code Style

### Python (Backend)
- **Python 3.11** required
- **4-space indentation**
- **snake_case** for functions/variables, **PascalCase** for classes
- **Mandatory type hints** on all function signatures
- Follow **PEP 8** style guide
- Use **Ruff** for linting and **mypy** for type checking
- Fix ALL warnings before committing

### TypeScript/React (Frontend)
- **2-space indentation**
- **PascalCase** for components (e.g., `CreateTask`)
- **camelCase** for hooks, utilities, variables
- **Functional components + Hooks** pattern
- Avoid `any` type - use proper TypeScript types
- Component structure: `src/pages/ComponentName/index.tsx` + `style.css`
- Run `npm run lint` before committing

## Testing

### Backend
- **Framework**: pytest + pytest-asyncio
- **Convention**: `backend/tests/test_*.py`
- **Coverage requirement**: ≥80% for modified modules
- Tests are configured in `backend/pytest.ini`

### Frontend
- Currently **manual testing**
- If adding complex logic, consider adding Vitest tests in `src/__tests__/`

## Zhipu AI Integration

The system supports Zhipu AI models as an evaluation target:

**Usage:**
- Set `agent_model` to `zhipu` (or any value starting with `zhipu`) when creating a task
- Use placeholder URL like `zhipu://chat` for `agent_api_url`
- Ensure `ZHIPU_API_KEY` is set in backend `.env`

**Example script:**
```bash
cd backend
source .venv/bin/activate
python app/examples/zhipu_chat_demo.py --prompt-var product_name=测试产品
```

**Multi-turn conversation:**
- Set `ZHIPU_DIALOG_MODE=multi` in `.env`
- Provide conversation history as JSON to the demo script

## Time Zone Handling

- **Display**: All times shown in frontend and exports are **Beijing Time (Asia/Shanghai, UTC+8)**
- **Storage**: Backend stores all timestamps in **UTC with timezone**
- **API responses**: Backend converts UTC to Beijing Time before returning
- **CSV exports**: Timestamps formatted as ISO 8601 with +08:00 offset

## Commit & PR Guidelines

### Commit Messages
Use **Conventional Commits** format:
- `feat(frontend): add task list pagination`
- `fix(backend): correct timeout handling in Celery task`
- `docs: update CLAUDE.md with Zhipu instructions`
- `refactor(services): extract agent adapter pattern`
- `test(api): add integration tests for task creation`

### Pull Request Requirements
- **Summary**: Clear description of changes and motivation
- **Testing**: Steps to verify the changes
- **Screenshots**: For UI changes
- **Checks**: Ensure `pytest`, `ruff`, `mypy`, and `npm run lint` all pass
- **Configuration**: Note any new `.env` variables or setup steps

## Security

- **Never commit** filled `.env` files or API keys
- Copy `.env.example` to `.env` and fill in secrets locally
- Backend: `storage/uploads/` is gitignored - clear before pushing if needed
- Frontend: Do not commit `dist/` directory
- Use environment variables for all sensitive configuration

## Development Workflow

1. **Setup environment**: Follow backend/frontend setup commands above
2. **Make changes**: Follow code style guidelines
3. **Test locally**: Run pytest (backend) and manual testing (frontend)
4. **Check quality**: Run linters and type checkers
5. **Commit**: Use conventional commit format
6. **PR**: Include all required information per PR guidelines

## Common Patterns

### Adding a New API Endpoint

1. Define Pydantic schema in `backend/app/schemas/`
2. Create route handler in `backend/app/api/routes/`
3. Implement business logic in `backend/app/services/`
4. Add repository methods if DB access needed in `backend/app/db/repositories/`
5. Write tests in `backend/tests/`

### Adding a New Frontend Page

1. Create directory in `frontend/src/pages/PageName/`
2. Add `index.tsx` (component) and `style.css`
3. Define route in `frontend/src/router.tsx`
4. Add API client methods in `frontend/src/api/`
5. Define TypeScript types in `frontend/src/types/`

### Working with Celery Tasks

- Tasks are defined in `backend/app/services/`
- Task state is tracked in PostgreSQL via custom result backend
- Check `backend/logs/celery.log` for task execution logs
- Rate limiting is controlled by `RATE_LIMIT_PER_AGENT` in `.env`

## Troubleshooting

**Backend won't start:**
- Ensure PostgreSQL and Redis are running
- Check `.env` has correct `DATABASE_URL` and `REDIS_URL`
- Run `alembic upgrade head` to apply migrations

**Celery worker fails:**
- Check Redis connection
- Verify `ZHIPU_API_KEY` if using Zhipu model
- Review `backend/logs/celery.log` for errors

**Frontend can't connect to backend:**
- Verify backend is running on port 8000
- Check `VITE_API_BASE_URL` in frontend environment
- Look for CORS errors in browser console

**Port 8000 already in use:**
- Run `lsof -iTCP:8000 -sTCP:LISTEN -nP` to find the process
- Kill existing process or change port in uvicorn command
