---
name: build-feature
description: End-to-end workflow for adding a feature to this app - plan mode, implementation, pytest, server restart, then Playwright verification in the browser. Use when the user asks to build, add, or implement a new feature, tab, endpoint, or UI section, or invokes /build-feature.
---

# Build Feature

Run the phases in order. Do not skip ahead; each phase gates the next.

## 1. Plan (plan mode)

1. Call `EnterPlanMode` before touching any file.
2. Explore first: read the closest existing view/endpoint and copy its patterns.
3. Use `AskUserQuestion` for real forks (data source, algorithm, UI scope). Max 2-3 options, recommended first.
4. The plan lists every affected file, the API contract, the test cases, and the browser checks.
5. Exit plan mode and wait for approval. No code before that.

## 2. Implement

- Any new or significantly changed `.vue` file goes to the **vue-expert** subagent (project rule). Brief it with the API contract and the files to match.
- Backend: update Pydantic models whenever the JSON shape changes. Declare static routes before `/{id}` routes.
- UI: slate palette, no emojis, labelled controls, focus states, `role="status"`/`role="alert"` for async feedback. Add keys to both `locales/en.js` and `locales/ja.js`.
- Read the vue-expert output yourself before moving on; do not trust the summary.
- Propagation: update the endpoint list in `CLAUDE.md` and any affected tests.

## 3. Test the backend

Use the `backend-api-test` skill for `tests/backend/`. Run from `server/`:

```bash
cd server && uv run --with pytest --with httpx pytest -c ../tests/pytest.ini --rootdir ../tests ../tests/backend -q
```

Fix failures before continuing. Tests that touch in-memory state need a reset fixture in `conftest.py`.

## 4. Restart both servers

The backend runs without reload, so new routes are invisible until it restarts. Always restart before browser testing.

1. Run `/start`. It kills ports 3000 and 8001, starts both servers, and verifies them.
2. Confirm the new routes exist: `curl -s localhost:8001/openapi.json | grep -o '"/api/[^"]*"'`.
3. If a stale process survives, `lsof -ti:8001 | xargs kill` and start again.

## 5. Verify with Playwright MCP

Playwright tools are deferred; load them with `ToolSearch` first. If the server is not connected, tell the user to run `/mcp` and stop - do not claim the UI works.

1. Navigate to `http://localhost:3000` and screenshot the dashboard.
2. Click every nav tab and confirm the `h2` renders.
3. Exercise the new feature end to end: the main interaction, the submit/save action, and where its result shows up elsewhere in the app.
4. Check keyboard use (focus the control, press arrow/End/Home/Enter) and switch to JA.
5. Read the console log. Compare against the known baseline: `/api/tasks` 404, unresolved `PurchaseOrderModal`, missing favicon. Report anything else.

Gotchas:
- Use `getByRole('link', { name: '...' })` as the click target; plain `link "Name"` is rejected.
- Debounced inputs need a 1s wait before reading results.
- Set range inputs through `evaluate` plus an `input` event.
- Screenshots land in the repo root. Read them, then delete them (`rm -f *.png`); `.playwright-mcp/` logs are scratch too.
- Test submissions persist in server memory. Say so in the report.

## 6. Report

State what was verified and what was not (keyboard, JA, edge cases). Flag pre-existing issues separately from new ones. Do not commit unless asked; never add a `Co-Authored-By: ... <noreply@anthropic.com>` line, and never commit `client/package-lock.json`.
