# Handoff — Orchestrate POC session (2026-08-04 → 2026-08-05)

Context for picking up where this session left off. Read this before touching
code.

## Where the repo stands right now

- Last **committed** commit: `d009a44` ("Replace Run Report with a
  chat-driven generate_report tool, and add a no-code Add Tool feature...").
  That commit already contains last session's work: chat-driven
  `generate_report` tool (per-agent chat only), the Add Tool feature, and
  the Data Source Registry fix (generic "Upload documents" section keyed
  off a `DATA_SOURCE_REGISTRY`, replacing hardcoded Holdings/Reconciliation
  sections).
- **Uncommitted on top of that**, from this session's work (see part 1
  below): `backend/app/api/main.py`, `backend/app/api/schemas.py`,
  `backend/app/platform/runtime/agent_chat.py`,
  `backend/app/platform/runtime/report_tool.py`,
  `backend/app/platform/runtime/supervisor.py`,
  `backend/tests/test_phase11_supervisor_routing.py`,
  `frontend/react_app/src/api/client.ts`,
  `frontend/react_app/src/pages/ChatPage.css`,
  `frontend/react_app/src/pages/ChatPage.tsx`,
  `frontend/react_app/src/state/chatHistory.ts`.
- Backend `py_compile` clean on all edited files. Frontend `npm run build`
  and `npm run lint` both clean. Backend tests
  (`test_phase7_api.py`, `test_phase11_supervisor_routing.py`) pass — real
  LLM calls, real Postgres, not mocked.
- A commit message was drafted (multiple times, shortened per the user's
  request each time) for the *previous* commit (`d009a44`) — that one's
  done. **No commit message has been drafted yet for this session's
  uncommitted work** (the report-approval-through-homepage-chat fix) — do
  that once the user asks, matching their preference for short (2-3 line)
  commit messages.

## Part 1: Fixed — homepage chat can now generate/approve reports

This was the main piece of work this session. Full detail already saved to
memory (`project_supervisor_chat_report_reverted.md`), summarized here.

**The bug (from a previous session):** the homepage's multi-agent chat could
route ad hoc questions to any included agent, but asking one to "generate
this month's report" would either silently fail to record the human's
approve/reject decision (200 OK, no audit log row — verified directly in
Postgres, reproduced 3x), or — a *second*, separately-discovered symptom —
just fabricate a full report-looking answer conversationally (since the
collaborator never actually had the `generate_report` tool wired in), with
no approval gate and no audit trail at all.

**Root cause, found this session via deep investigation (not guessed):**
the *previous* session's "best working theory" (rebuilding the supervisor
fresh per request breaks resume) was investigated in depth and **ruled
out** — `langgraph_supervisor` actually does correctly detect a
supervisor-wrapped collaborator as a real nested subgraph via an
AST/closure-inspection mechanism (`find_subgraph_pregel` in
`langgraph/pregel/_utils.py`), so that theory doesn't hold up.

The *actual* root cause: `generate_report`'s tool body called `interrupt()`
a second time, on top of the report pipeline's own separate, correctly
checkpointed interrupt — trying to also freeze the outer *chat's own
conversation graph*. Per LangGraph's own docs, resuming a node "resumes
from the start of the node, re-executing all logic." For a single agent's
own chat, the interrupted node happens to be just the ToolNode step (no LLM
call needed to replay it) — so this happened to work reliably there. But
wrapped inside `langgraph_supervisor`, the *whole collaborator turn*
(including its own fresh LLM call) is what gets replayed on resume — and a
freshly re-invoked LLM has no memory that it already decided to call the
tool, so it may just answer plainly without ever reaching `interrupt()`
again. That's exactly the observed symptom.

**Confirmed against the real product** (via the newly-connected `wxo-docs`
MCP server — see Part 2): real watsonx Orchestrate avoids this whole
failure class by design. A Flow needing human approval runs as an
independent, addressable instance (an "instance ID"), decoupled from
whatever chat triggered it — checkable even from a brand new chat session,
per IBM's own docs. Never a resumed conversation graph.

**The fix, mirroring that pattern:**
- `generate_report` (`backend/app/platform/runtime/report_tool.py`) no
  longer calls `interrupt()` at the chat level — it just returns a plain
  string noting the report is pending.
- New `get_pending_report(instance_id, workflow_config, checkpointer)` —
  reads the pipeline's own pending-interrupt state directly via
  `pipeline.get_state(...)`, no invocation needed.
- New `submit_report_decision(instance_id, workflow_config, checkpointer,
  *, decision, actor, comment)` — resumes the pipeline directly by instance
  id, independent of any chat's graph.
- `GENERATE_REPORT_TOOL_NAME` constant added (used by `main.py`'s message
  diffing, see below).
- `agent_chat.py`/`supervisor.py`: `include_report_tool=True` is now safe
  for supervisor collaborators too (was per-agent-chat-only before).
  `build_chat_supervisor`'s collaborators now get `checkpointer=checkpointer,
  include_report_tool=True`. `create_supervisor(..., output_mode=
  "full_history")` added so a collaborator's `generate_report` ToolMessage
  is actually visible in the supervisor's own message state (needed for the
  next point).
- `main.py`: both `/agents/{id}/chat` and `/chat` now only surface
  `pending_approval` if `generate_report` was **actually called this
  specific turn** (a `_generate_report_called` helper diffs message counts
  before/after `.invoke()`) — otherwise a stale pending report from days
  ago would silently overwrite the answer to an unrelated new question.
  `/agents/{id}/chat/decision` no longer touches the agent's own graph at
  all — just calls `submit_report_decision` directly. New `POST
  /chat/decision` endpoint (homepage) takes `agent_id` in the body
  (`HomeChatDecisionRequest`, since more than one collaborator could be
  involved) and does the same direct resume.
- `schemas.py`: `PendingApprovalOut` now carries `agent_id`; new
  `HomeChatDecisionRequest`.
- Frontend: `client.ts` (`PendingApproval.agent_id`,
  `HomeChatDecisionRequest`, `api.submitChatDecision`), `chatHistory.ts`
  (new `"approval"` message role + `actor`/`comment`/`deciding` state,
  mirroring `agentChatHistory.ts`'s existing per-agent pattern),
  `ChatPage.tsx`/`ChatPage.css` (renders the same inline approval card the
  per-agent chat already had, wired to the new decision endpoint).

**Verified live (real LLM + Postgres, not mocked):**
`test_phase11_supervisor_routing.py::test_chat_generate_report_through_homepage_supervisor_then_approve`
— builds the supervisor directly from one isolated test instance (not via
the real `/chat` endpoint) specifically so it can't accidentally route to,
and write a decision against, one of the project's real agents. That
happened once while writing this test (see "known incident" below). All 6
tests across `test_phase7_api.py` + `test_phase11_supervisor_routing.py`
pass, except one known-flaky pre-existing test unrelated to this fix (next
point). **Not yet verified in the actual browser UI** — the new approval
card in the homepage chat has only been tested via the backend/API layer so
far.

**Known incident, already resolved:** the first attempt at the new
regression test accidentally routed to the user's own **real** agents (id
66 "Meezan stock reconcilliation", id 71 "Compliance report") because
they're currently marked `included_in_chat=True` in the live shared dev DB.
This left agent 71 with a freshly re-generated pending report (overwriting
its previously-approved state from Aug 3). The user was asked how to
resolve it and chose "approve it" — done, audit log id 111. The test itself
was then rewritten to build the supervisor directly from an isolated
instance so this can't happen again.

**Known pre-existing, unrelated fragility, not fixed (out of scope):**
`test_chat_routes_between_two_included_agent_instances` in the same test
file asserts an exact routed-to agent name, but `/chat` queries *every*
`included_in_chat=True` deployed instance in the live shared dev DB — since
real agents (66, 71) are kept included in chat from manual testing, this
test can flake by routing to one of them instead of its own synthetic
fixtures. This predates this session; not something to "fix" without being
asked, just don't mistake it for a new regression if it flakes again.

## Part 2: MCP servers now connected — reconnect these in a fresh session if needed

Three HTTP MCP servers are configured at the **project level** (in
`~/.claude.json`, key path
`projects["c:/Users/hasan/Desktop/IBM-POC"].mcpServers` — note forward
slashes in that key, unlike the Windows path elsewhere):

```
docs-langchain      -> https://docs.langchain.com/mcp
reference-langchain -> https://reference.langchain.com/mcp
wxo-docs            -> https://developer.watson-orchestrate.ibm.com/mcp
```

- `docs-langchain`/`reference-langchain` were already present from an
  earlier session (not added this session).
- `wxo-docs` was added **this session**, explicitly, via:
  ```
  claude mcp add --transport http wxo-docs https://developer.watson-orchestrate.ibm.com/mcp
  ```
  Confirmed actually working with a real query (not just "listed") —
  returned genuine IBM ADK doc content on human-in-the-loop Flow behavior,
  which directly informed Part 1's fix above.
- Important distinction: `wxo-docs` is the **documentation-only** MCP
  server (real-time search over IBM's actual ADK docs via
  `mcp__wxo-docs__search_ibm_watsonx_orchestrate_adk` and
  `mcp__wxo-docs__query_docs_filesystem_ibm_watsonx_orchestrate_adk`). It is
  **not** the full ADK CLI server that controls a real running Orchestrate
  instance (that would additionally require installing IBM's local
  "Developer Edition" server separately — discussed, not done, deferred by
  the user "get back on this later").
- If a fresh session doesn't see these tools available, they may need
  reconnecting — the config above is the ground truth to restore from if
  `claude mcp list` needs re-adding entries (that command's health check
  was flaky/incomplete when tested this session — showed only the
  unrelated Figma server as connected despite wxo-docs demonstrably
  working — don't trust its output alone, check the config file directly if
  in doubt).

## Part 3: Cross-check against real IBM docs — researched, not yet acted on

Once `wxo-docs` was confirmed working, ran 5 parallel research agents
cross-checking this repo's actual implementation against real watsonx
Orchestrate ADK documentation, area by area. Findings below, roughly
ordered by how much each actually matters — **none of these have been
built yet**, this is the queue to pick from:

1. **Compliance checks aren't deterministic (highest-priority finding).**
   The Reconciliation agent's ledger-vs-custodian matching is 100%
   deterministic code (`compute_position_matches` in
   `backend/app/platform/tools/reconciliation.py` — exact numbers, no LLM
   guessing). But the Compliance agent's BREACH/PASS calls (liquidity 5%,
   single-issuer 10%, sector 20%, Shariah list) are currently **LLM
   judgment over retrieved text**, not an actual threshold comparison in
   code. Real Orchestrate has a dedicated "Decisions node" for exactly this
   (a rule table evaluated in code). This is a genuine inconsistency
   between the two pipelines in this same repo — one treats math as
   sacred, the other doesn't.

2. **Knowledge/RAG — mostly validated, two real gaps.** The two-track split
   (chunked RAG for regulatory text vs. deterministic extraction for
   tabular data, in `extract.py` vs. `ingest.py`/`retrieval.py`) matches
   IBM's own documented anti-pattern guidance almost verbatim — good sign,
   not an accident. Two real gaps found: (a) zero overlap between RAG
   chunks (`backend/app/platform/rag/chunking.py` — IBM recommends 10-20%
   overlap so a clause split across a boundary doesn't lose context); (b)
   no version/effective-date metadata on uploaded regulatory documents —
   IBM calls "assumed trust in the knowledge source" the *highest-risk*
   anti-pattern, and for a compliance agent specifically, a stale mandate
   clause currently looks identical to a current one.

3. **Multi-agent routing.** Confirmed for real (not just plausible, per
   actual doc passages) that "Add Agent to a specific agent" (fixed,
   build-time roster — the deferred feature, see
   `project_add_agent_deferred.md`) and "the shared default/homepage chat"
   (dynamic, session-time) are genuinely two different documented concepts
   in real Orchestrate. New idea surfaced: real Orchestrate has a
   `mentions`/`assistant_id` field for addressing one specific agent
   within a shared chat, per message — a much cheaper way to get an
   "@-mention a specific agent" capability than building the full deferred
   Add-Agent roster feature. Also a **zero-code-change** actionable item:
   IBM's guidance says agent descriptions should mention their tools/
   knowledge, not just their domain — worth rewriting the actual deployed
   agents' descriptions in the DB, since that's literally what
   `supervisor.py`'s `_routing_prompt` routes on.

4. **Tools & agent definition — smaller, all optional.** Tool docstrings
   could be tightened to Google-style Args/Returns for IBM-convention
   consistency (cosmetic). `DATA_SOURCE_REGISTRY` has no IBM equivalent —
   that's fine, it solves a problem specific to reading pre-uploaded files
   that IBM's tools don't have (theirs call live APIs). Cheap UI fix: the
   Profile tab's Description field has no guidance hint steering toward
   "when to use this agent," unlike the Behavior tab which already does —
   worth matching, since Description is what routing actually uses.
   `llm_config` (temperature/max_tokens overrides) is a real IBM concept
   skipped entirely — optional, cheap if per-agent tuning is ever wanted.

The user was last asked which of these to act on first — no answer given
yet before this handoff was written.

## Standing user preferences (apply throughout, not just this session)

- **Never leave dev servers running.** Kill anything started via Bash for
  a live smoke test before ending the turn. User runs their own
  frontend/backend manually and prefers it that way.
- Give feedback + a concrete technical plan **before** building each new
  feature; wait for explicit go-ahead rather than assuming approval from a
  discussion message. For simple exploratory questions, a short (2-3
  sentence) recommendation is preferred over an exhaustive options survey.
- Verify claims with real, live tests (real LLM calls, real Postgres
  checks) rather than code-review-only confidence. This session's report-
  approval fix and the earlier Data Source Registry fix were both verified
  this way.
- When something doesn't work as hoped, say so plainly and revert/fix
  cleanly rather than leaving a half-working, misleading feature in place.
- Terse, direct answers preferred generally; avoid jargon unless the user
  has clearly demonstrated familiarity with it. Ground explanations in
  visible website behavior, not internal field/variable names, unless
  asked for technical depth.
- Commit messages: short — 2-3 lines max, per explicit repeated request
  this session.
- Before any destructive-ish git operation, check `git status` first (this
  repo currently has real uncommitted work, see "Where the repo stands"
  above — don't `git reset`/`checkout`/`clean` without stashing/committing
  first).

## Likely next steps (not decided, just the visible queue)

1. Decide which Part 3 cross-check finding to act on first (compliance
   determinism is the one actually affecting correctness; the rest are
   lower-stakes polish).
2. Commit this session's uncommitted report-approval fix (Part 1) — draft
   a short (2-3 line) commit message when asked, don't commit unprompted.
3. Do an actual browser-level smoke test of the new homepage chat approval
   card — backend is fully verified, frontend UI for this specific feature
   isn't yet.
4. Still open from before this session: agent 71's original corrupted-
   holdings issue (separate from the pending-report incident above,
   already resolved) — check `project_data_source_registry_open_decision.md`
   for whether `fund_holdings_dataset.xlsx` still needs re-uploading.
5. Still deferred, not urgent: the full Add Agent (fixed collaborator
   roster) feature — see `project_add_agent_deferred.md`. The mentions/
   assistant_id idea from Part 3 above is a cheaper alternative worth
   considering instead, if per-turn manual agent addressing is ever wanted.
6. Not started: the Channels tab (deployment/embed) — still a literal
   placeholder.
