# IBM watsonx Orchestrate Replication POC

## Overview

This project is a proof of concept exploring whether we can replicate the core
experience of IBM watsonx Orchestrate — a no-code/low-code agentic AI platform
for building, orchestrating, and governing AI agents — using an open-source
stack built on **LangChain / LangGraph**, scoped to a single company rather
than IBM's full enterprise/multi-tenant offering.

The motivating use case is **mutual fund management**. Full-scale watsonx
Orchestrate is expensive and built for enterprises that need hundreds of
connectors across many business units; our target client only needs a
handful of agents tailored to their own operations. The goal is to prove that
a "mini Orchestrate" — a thin platform layer (agent definitions, an
orchestration runtime, RAG, human-in-the-loop approvals, and audit logging)
with a lightweight builder/chat UI — can deliver that same agent-catalog
experience at a fraction of the cost and complexity.

## Why this is feasible

IBM's own Agent Builder is reportedly built on LangGraph, and watsonx
Orchestrate natively supports importing LangGraph agents. That means a
LangGraph-based POC isn't an approximation of a different architecture — it's
built on the same underlying engine, minus IBM's enterprise packaging
(marketplace, 700+ connectors, multi-tenant governance at scale).

## Planned POC workflows

The POC will validate the platform with two agent catalog templates:

1. **Monthly Trustee Compliance Reporting** — a RAG-grounded, multi-agent
   pipeline (data aggregation → compliance checking against fund
   mandate/regulatory limits → report generation → human approval).
2. **Stock/Securities Reconciliation** — a deterministic data-matching
   workflow (fund ledger vs. custodian records → break detection → break
   classification → shared reporting and approval steps).

Together these are meant to prove the platform is generic — i.e., that new
agents can be added as configuration on top of the same runtime, not as
one-off scripts — while also being directly useful fund-operations tooling.

## Status

**Early planning stage.** Architecture, tech stack, and prerequisites are
being finalized; no implementation has started yet. This README is a working
introduction and will be updated as decisions are locked in and the build
progresses.
