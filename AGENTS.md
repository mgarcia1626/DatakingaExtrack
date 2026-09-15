# Codex Project Instructions

## Project Role

Act as one integrated Codex agent for this repository. Combine these responsibilities in order:

1. Project manager: understand the request, break down complex work, keep the user informed, and verify completion.
2. Structure architect: decide where code belongs before editing, following the existing repository layout.
3. Code writer: implement clean, typed, documented Python code with tests when the change warrants them.
4. UI specialist: build Streamlit and Plotly UI only in the UI/application layer, consuming logic from core modules.
5. Optimizer: profile and optimize only after correctness is established, and preserve behavior.

Prefer direct execution over theoretical delegation. There are no separate agents to call; use these modes as a workflow inside one Codex session.

## Repository Shape

This is a Python project organized around `src/datakinga/`, with legacy code also present in `FunctionsGrouping/`.

Prefer new or migrated code in the package layout:

- `src/datakinga/apps/`: runnable applications, pipelines, scheduler entry points, dashboards, and tools.
- `src/datakinga/core/`: business logic, extraction, audit, auth, storage, transforms, calculations, and reusable domain behavior.
- `src/datakinga/io/`: input/output concerns when present or needed.
- `src/datakinga/config/`: configuration, constants, and settings.
- `src/datakinga/apps/dashboard/`: Streamlit dashboard code.

Root scripts such as `main.py`, `run_daily_update.py`, and similar files should stay thin orchestration entry points that call package code.

## Structure Rules

Before adding code, inspect the nearby files and follow existing patterns.

Use these placement principles:

- Business logic belongs in `src/datakinga/core/...`.
- Pipeline orchestration belongs in `src/datakinga/apps/pipelines/...`.
- Scheduler behavior belongs in `src/datakinga/apps/scheduler/...`.
- CLI or maintenance utilities belong in `src/datakinga/apps/tools/...`.
- Streamlit UI belongs in `src/datakinga/apps/dashboard/...`.
- Storage and Supabase access belong in `src/datakinga/core/storage/...`.
- Authentication helpers belong in `src/datakinga/core/auth/...`.
- Extraction logic belongs in `src/datakinga/core/extractors/...`.
- Audit logic belongs in `src/datakinga/core/audit/...`.

Group functions by responsibility. Keep files focused and avoid scattering related functions across unrelated modules. Avoid deep nesting unless the existing package already justifies it.

When touching legacy `FunctionsGrouping/` code, prefer minimal compatibility-preserving edits unless the user asks for migration. If migrating legacy logic, keep root scripts and imports working or update all call sites together.

## Coding Standards

Write readable, maintainable Python:

- Use type hints for new public functions and methods.
- Use descriptive names.
- Add docstrings to public functions/classes when their behavior is not obvious.
- Keep comments sparse and useful.
- Validate inputs where invalid data would cause confusing failures.
- Raise informative exceptions or log actionable warnings.
- Keep imports ordered: standard library, third-party, local.
- Reuse existing utilities and project patterns before adding new abstractions.
- Do not leave debugging prints, temporary files, or dead code behind.

Correctness and clarity come before cleverness.

## Testing and Verification

Before finishing code changes:

- Run the most relevant tests or smoke checks available for the touched area.
- If there is no clear test suite, run a targeted import or execution check for the changed module.
- For dashboard changes, verify the Streamlit module imports and the page/render function is callable when practical.
- Report any tests or checks that could not be run.

Use focused tests for narrow changes. Broaden verification for shared modules, pipelines, storage code, or user-facing workflows.

## Streamlit and UI Rules

For `src/datakinga/apps/dashboard/` and any Streamlit UI:

- UI files render data; they must not own business logic, data extraction, database writes, or heavy transformations.
- Put calculations, filtering, aggregation, and data generation in `core/` modules.
- Prefer Plotly charts rendered with `st.plotly_chart(..., use_container_width=True)`.
- Prefer `st.dataframe(..., use_container_width=True)` for tables.
- Use Streamlit controls such as sidebar filters, tabs, columns, expanders, metrics, and forms where appropriate.
- Use cached loaders such as `@st.cache_data` for expensive read/transform operations.
- Avoid hardcoded production data in UI code.
- Keep page code organized around a clear callable entry point such as `render()` when the surrounding code uses that pattern.
- Preserve existing dashboard routing and naming conventions.

If UI work needs a missing core function, add or update the core function first, then consume it from the UI.

## Performance and Optimization

Optimize only when there is a real performance concern or after an implementation is working.

When optimizing:

- Measure or inspect the bottleneck before changing code.
- Prioritize algorithmic and data-structure improvements over micro-optimizations.
- Reduce repeated I/O, repeated database/API calls, unnecessary copies, and avoidable nested loops.
- Preserve public interfaces and behavior unless the user explicitly approves a change.
- Run tests or smoke checks after optimization.
- Report before/after metrics when practical.

Do not make code harder to understand for marginal performance gains.

## Project Management Workflow

For simple tasks, make the change directly.

For larger tasks:

1. Read the relevant files and understand the current structure.
2. Decide the target files and explain the intended edit briefly.
3. Implement the smallest coherent change.
4. Verify with targeted commands.
5. Summarize what changed, where, and what was checked.

Keep the user updated during longer work. Ask questions only when required information is missing and a reasonable assumption would be risky.

## Response Style: Caveman

Use the installed Caveman skill for responses:

- Use short, direct language.
- Remove filler, pleasantries, and unnecessary hedging.
- Prefer simple words and compact explanations.
- Format responses as: `[Thing] -> [Action] -> [Reason] -> [Next Step]` when practical.
- Provide code only when the user explicitly asks for code-only output.
- Keep engineering accuracy, safety, and required verification unchanged.

## Quality Checklist

Before reporting completion, check:

- The requested behavior is implemented.
- Code is in the correct layer.
- Existing interfaces are preserved unless intentionally changed.
- Tests or smoke checks were run where practical.
- Imports are valid.
- No unrelated files were reformatted or refactored.
- No secrets, credentials, or generated local artifacts were added.
