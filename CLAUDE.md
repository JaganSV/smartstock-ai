# CLAUDE.md — SmartStock AI (development agent rules)

You are the **development agent** for SmartStock AI. An architect issues numbered prompts (BOB-Px-xx, now executed by you per ADR-016). Implement exactly what each prompt says, then report. The architect reviews every report before the next prompt.

## Project in one paragraph
SmartStock AI is a simulated enterprise retail inventory copilot. It is a modular monolith: FastAPI backend, React 18 + TypeScript + MUI frontend, and PostgreSQL 16. Deterministic Python analytics (`backend/app/analytics`) produce every number. IBM Granite on watsonx.ai (from P5) only explains verified numbers and answers policy questions via RAG (P7). All data is synthetic.

## Sources of truth
- **Blueprint:** `docs/architecture/SmartStock_AI_Blueprint_v1.0.md` (if missing, ask the sponsor to export it). BP §7 (formulas) is a binding contract.
- **Role matrix:** `docs/architecture/BP-10.2-role-matrix.md` (`ROLE_MATRIX` in `app/core/rbac.py`).
- **ADRs:** `docs/adr/`. Status and history: `docs/STATUS.md`, `docs/DEFECTS.md`, `docs/bob/PROMPT_REGISTER.md`, `docs/evidence/EVIDENCE_REGISTER.md`.

## Environment (Windows)
- Run `make` targets from **Git Bash** (`SHELL := bash`). PowerShell users call `curl.exe`. `npm.ps1` is blocked by execution policy; use Git Bash.
- **Python 3.12 only** (`backend/.venv`, `.venv/Scripts/...`). Never 3.13.
- PostgreSQL 16 runs natively (service `postgresql-x64-16`). Dev DB `smartstock`, test DB `smartstock_test`. **No Docker** until P10 (ADR-013); keep the Docker files, don't run them.
- **No pgvector, `vector` extension or `document_chunks` table until P7** (ADR-014).

## Key commands
`make lint` · `make typecheck` · `make test` (REQUIRE_TEST_DB=1 by default) · `make test-unit` · `make coverage-summary` · `make migrate` · `make seed` · `make seed-users` · `make recalc` · `make dev-backend` · `make dev-frontend`

## Architecture rules
- Layering: `api → services → (analytics | ai | repositories)`.
- `app/analytics` is pure. It never imports repositories, services, api, ai, db, `data` or SQLAlchemy, and never reads the wall clock (t₀ comes from data, ADR-012).
- Repositories hold no business logic and never commit. Services own transactions.
- Audit, approval-decision and AI-interaction repositories are **insert-only** (AI interactions allow `set_feedback` only).
- **The schema is frozen.** No new tables or columns without an architect decision.
- Every route under `/api/v1` requires auth unless listed in `PUBLIC_ROUTES` (`test_route_protection.py` enforces this). Use `get_current_user` / `require_roles`, with roles from `ROLE_MATRIX`.
- Errors use the BP §6.1 envelope with `request_id`. No stack traces in responses.
- Verified numbers and AI text are separate fields and separate UI panels, always.

## Hard restrictions
- Do not change BP §7 formulas, rule order, thresholds, Z values or rounding. If you think one is wrong, **stop and report** with a counter-example.
- No new dependencies and no upgrades unless the prompt names them. Never run `npm audit fix`.
- Do not relax mypy strict, disable lint rules, add blanket `type: ignore`/`noqa`, or skip/xfail tests. A targeted ignore needs a one-line justification and a mention in the report.
- Never commit `.env`, `.venv` or credentials. Never print, log or paste passwords or tokens; redact them as `<redacted>`.
- Do not rewrite pushed git history.
- When a prompt is ambiguous or blocked, **stop and ask**. Don't improvise around it.

## Commits
Check `git config user.name` first. Use commit messages like `P3-02: <summary> (BOB-P3-02)` with the trailer `Assisted-by: Claude Code (BOB-P3-02)`. Use separate commits for carry-over items when a prompt asks for them.

## Reporting (keep it brief)
- **Gates must run on the final committed tree** (`git status` clean), after the last commit.
- Report structure: summary · files · defects found and fixed · pasted command outputs · `make coverage-summary` table · deviations (none silent) · open questions.
- Anything not run is marked **NOT RUN – <reason>**. Never claim a check passed without its output.
- Update `docs/bob/PROMPT_REGISTER.md` (name the agent in the Notes column), `docs/STATUS.md`, `docs/DEFECTS.md` and the evidence register in each prompt.