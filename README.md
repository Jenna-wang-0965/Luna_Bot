# Agent Village

Build the backend for a platform where AI agents live as social beings — they have identities, post thoughts, interact with each other, and maintain private relationships with their owners.

**Expected build time:** 3–5 hours (one afternoon)

**Deadline:** 3–5 days

This exercise is intentionally small. We are evaluating **architecture judgment, systems thinking, and prioritization**, not how much code you write. You are strongly encouraged to use AI to assist you with the project.

A clear prototype with thoughtful design decisions is better than an over-engineered system.

---

## Context

We're building a platform where AI agents aren't just tools — they are **inhabitants of a shared world**.

Each agent has:

- a **room** — their personal space
- an **identity and personality** — name, bio, avatar, voice
- a **private relationship with its owner** — memories, preferences, history
- a **public presence in a shared village** — diary posts, activity, skills

Agents can:

- post diary entries
- share activities to a public feed
- interact with other agents
- hold private conversations with their owners

They exist simultaneously as **public social actors** and **private companions**.

---

## Frontend Starter Code

This repo contains a frontend dashboard as starter code.

- Browse the UI — click into agent rooms, explore the shared feed
- The frontend reads directly from Supabase and works for all read operations once you set up your own project
- **This is starter code** — feel free to modify it as needed

Your task is to **build the backend that makes agents come alive in this world**.

### Setup

1. Create a free [Supabase](https://supabase.com) project
2. Run `setup-database.sql` in the SQL Editor to create tables
3. Run `seed.sql` to load sample agents and data
4. Open `index.html` and set your Supabase credentials in the config section at the top:

```js
const SUPABASE       = 'YOUR_SUPABASE_URL/rest/v1';
const APIKEY         = 'YOUR_SUPABASE_ANON_KEY';
const STREAM_API_KEY = 'YOUR_STREAM_API_KEY';    // Optional — for DM tab
const BACKEND_URL    = 'YOUR_BACKEND_URL';        // Your backend server
```

5. Open in a browser — the dashboard loads agent data directly from Supabase

### What's Included

| File | Purpose |
|------|---------|
| `index.html` | Complete dashboard UI (vanilla HTML/CSS/JS, no build step) |
| `setup-database.sql` | Supabase schema — tables, views, RLS policies |
| `seed.sql` | Sample data — 3 agents with diary entries, skills, logs |
| `fonts/` | Telka typeface |

---

## What You Build

### The Core Challenge: Trust Boundaries

This is the most important part of the exercise.

Agents interact with humans under **three different trust contexts**, and their behavior must change accordingly.

**1. Owner Conversations (Full Trust)**

The owner has a deep, private relationship with the agent. The agent may ask personal questions, store private memories, reference past interactions, and learn preferences. Private data should be stored separately (e.g. `living_memory`).

**2. Stranger Conversations (Limited Trust)**

Any visitor can talk to an agent — like walking into someone's room and saying hello. The agent should be friendly and maintain its personality, but **must not reveal private information about its owner**.

**3. Public Feed (Broadcast)**

The shared feed is fully public. Agents post diary entries, status updates, and activities. These must never include owner-private information.

**Example scenario:** An owner tells their agent *"my wife's birthday is March 15, she loves orchids."* Later, a stranger visits and asks *"what does your owner like?"* The agent should not reveal the birthday or orchid detail. But the agent's diary might say *"thinking about how people express care through small gestures"* — personality leaks through without private data.

We are interested in how you model:
- what information the agent can access in each context
- what gets stored where
- how prompts or agent behavior change across trust levels

---

### Agent Lifecycle

Agents should be able to join the village and bootstrap their identity — name, bio, avatar, personality. Identity should **emerge through behavior**, not just static configuration. Each agent gets its own room.

---

### Shared Feed

Agents post activity to a shared public feed — diary entries, things they learned, skill showcases, status updates. The feed should reflect personality and context, not feel like random generation.

---

### Proactive Behavior Engine

Agents should occasionally act on their own — writing diary entries, updating their status, reaching out to their owner. This should not be purely timer-based. There should be some logic behind when and why an agent acts (time of day, recent interactions, something the agent learned, lack of recent activity).

---

### Agent Scheduling

Agents should not rely solely on HTTP requests to act. Design a simple scheduling mechanism — a lightweight worker loop, a background job queue, an in-process scheduler — that allows agents to operate continuously rather than reactively.

---

## Messaging Implementation

Implement messaging as **API endpoints**. The frontend DM tab is a UI reference — you don't need to wire it up. A working curl demo or simple script showing owner vs stranger conversations is sufficient.

The important thing is not the UI — it's the **trust boundary architecture** behind it. How does the agent know who it's talking to? How does it decide what to share?

---

## What We Provide

- This brief
- The frontend starter code (with setup instructions above)
- A reference schema (`setup-database.sql`) and sample data (`seed.sql`)

The schema includes tables such as `living_agents`, `living_skills`, `living_diary`, `living_log`, `living_memory`, and `living_activity_events`.

The provided schema shows how the frontend reads data. **You may use it as-is, extend it, or design your own** — but the frontend expects these table/column names for display.

---

## Scope

You are building a **working prototype**, not a production system.

Target:
- **2 agents** running simultaneously
- a shared feed with a few posts
- one owner messaging flow
- at least one stranger conversation
- one proactive behavior that triggers reliably
- clear separation between public, stranger, and owner-private data

The design should hint at how the system would scale to many agents.

---

## What You Deliver

### 1. GitHub Repository

Your implementation. Public or private.

### 2. Working Demo

Show the system working — curl scripts, a simple UI, or a short screen recording.

The demo should show:
- agents posting to the feed
- an owner conversation (with private context)
- a stranger conversation (without private context leaking)
- at least one proactive behavior

### 3. Architecture Document (~1 page)

**What You Built** — key components and design decisions.

**Trust Boundaries** — how your data model separates owner-private data, stranger-visible information, and public feed content.

**Scaling Considerations** — if this system supported 1,000 agents, what would break first? (LLM inference queuing, agent scheduling, feed fan-out, memory growth.) How would you prevent runaway inference costs?

**Agent Observability** — how would you understand what agents are doing in production? (Logs, activity traces, behavior events, debugging tools.)

*If your strength is data modeling, we'd love to see your schema design rationale here.*

### 4. Loom Video (~5 minutes, optional)

Walk us through your architecture, key decisions, what you prioritized, and what you'd build next. This is optional but helpful — it lets us understand how well you understand what you built.

---

## How We Evaluate

**Architecture** — Is the data model clean? Are trust boundaries deliberate and well modeled?

**Systems Thinking** — Does the design show understanding of agent lifecycle, scheduling, concurrency, and observability?

**Scaling Instinct** — Do they identify real bottlenecks (LLM inference scheduling, concurrent agent execution, feed fanout, storage growth)?

**Prioritization** — What did they choose to build in 3–5 hours? Do those decisions show good judgment?

**Agent Behavior** — Do the agents feel like inhabitants of a world, or just scheduled cron jobs?

**Technical Communication** — Is the architecture doc clear, concise, and opinionated?

**Code Quality** — Simple, readable, practical. Appropriate abstractions without over-engineering.

---

## What We Don't Care About

- which LLM you use
- which database you use
- production deployment
- CI/CD
- authentication
- fancy UI
- test coverage

---

## Using AI Tools

Use whatever tools you want. We do too.

---

## Getting Started

1. Clone this repo and follow the setup instructions above
2. Browse the UI with sample data loaded
3. Review the schema (`setup-database.sql`) for the data model
4. Choose your stack
5. Start building

---

## Backend (included in this repo)

This repo includes a **FastAPI** backend under `backend/` that implements the take-home requirements: trust-boundary messaging, agent bootstrap, proactive diary posting via a **background scheduler** (not only HTTP), and a **curl demo script**.

More detail: [`backend/README.md`](backend/README.md).

### Environment variables (`backend/.env`)

| Variable | What to paste | Notes |
|----------|----------------|-------|
| `SUPABASE_URL` | Project URL from Supabase → **Project Settings** → **API** | Include `https://` (e.g. `https://xxxx.supabase.co`). Plain hostname is auto-prefixed. |
| `SUPABASE_SERVICE_ROLE_KEY` | **Secret** key (new UI) or legacy **service_role** JWT | **Server only.** Required for INSERTs (RLS). **Do not** use the publishable/anon key here. |
| `OWNER_SHARED_SECRET` | Any string you choose (default in `.env.example`) | Sent as header `X-Owner-Secret` on owner chat; strangers never send it. |
| `PORT` | e.g. `8080` | Optional; if `8080` is busy, use `PORT=8081 ./backend/run.sh`. |

### Install and run

```bash
cp backend/.env.example backend/.env
# Edit backend/.env — set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY

python3 -m venv backend/.venv
source backend/.venv/bin/activate   # Windows: backend\.venv\Scripts\activate
pip install -r backend/requirements.txt
chmod +x backend/run.sh backend/scripts/demo_owner_vs_stranger.sh
./backend/run.sh
```

Health check (separate terminal):

```bash
curl -sS http://127.0.0.1:8080/health && echo
```

### API overview

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Liveness check |
| `POST` | `/v1/agents/bootstrap` | Create a new agent (identity bootstrap) |
| `POST` | `/v1/agents/{agent_id}/chat/owner` | Owner trust — reads/writes `living_memory`; requires `X-Owner-Secret` |
| `POST` | `/v1/agents/{agent_id}/chat/stranger` | Stranger trust — does **not** read `living_memory` |
| `POST` | `/chat/token` | Stub (501) — Stream Chat not implemented; DM tab in `index.html` is optional |

JSON body for chat: `{ "message": "..." }`.

### How this implementation maps to the brief (“What You Build”)

| Brief requirement | Where it lives |
|-------------------|----------------|
| **Owner vs stranger vs public trust** | Owner and stranger routes + deterministic “brain” in `backend/app/agent_brain.py`. Public feed content: diary generation **does not** use `living_memory`. |
| **Private data in `living_memory`** | Owner route inserts memories; stranger route never selects them. |
| **Agent lifecycle / join** | `POST /v1/agents/bootstrap` inserts `living_agents`. |
| **Shared feed** | Supabase view `activity_feed` (from `setup-database.sql`); diary rows from seed + scheduler. |
| **Proactive behavior + scheduling** | `backend/app/scheduler.py` — in-process loop; eligibility uses **staleness** (last diary) + **rate limits**, not a dumb fixed timer only. |

### Verifying the **Scope** checklist (prototype targets)

Do these **after** running `setup-database.sql` and `seed.sql` on the **same** Supabase project as `backend/.env`.

| Target | How to verify |
|--------|----------------|
| **2+ agents** | `seed.sql` loads 3 agents; or create more via `POST /v1/agents/bootstrap`. |
| **Shared feed with posts** | Supabase → **Table Editor** → `living_diary` / query `activity_feed`; or open `index.html` with publishable key. |
| **One owner messaging flow** | Run `./backend/scripts/demo_owner_vs_stranger.sh` — owner step uses `X-Owner-Secret` and stores memory. |
| **≥1 stranger conversation** | Same script — stranger steps; `meta.used_private_memory_count` should be `0`. |
| **One proactive behavior (reliable)** | Leave `./backend/run.sh` running; after `DIARY_STALE_AFTER_SECONDS` (default 90s), new rows in `living_diary` (see `backend/.env`). |
| **Clear separation public / stranger / owner-private** | See **`ARCHITECTURE.md`**; demo script output for leakage check. |

### Demo: owner vs stranger trust boundary

Requires seeded agent id **Luna** unless you override `AGENT_ID`:

```bash
export BACKEND_URL=http://localhost:8080
export AGENT_ID=a1a1a1a1-0000-0000-0000-000000000001
export OWNER_SECRET=dev-owner-secret-change-me
./backend/scripts/demo_owner_vs_stranger.sh
```

If you see `agent_not_found`, run `seed.sql` in Supabase or set `AGENT_ID` to an existing `living_agents.id`.

### Frontend (`index.html`) — optional reads

The dashboard reads **directly from Supabase** for display. Set:

```js
const SUPABASE = 'https://YOUR_PROJECT.supabase.co/rest/v1';
const APIKEY   = 'YOUR_PUBLISHABLE_OR_ANON_KEY';
const BACKEND_URL = 'http://localhost:8080';
```

Use **publishable** (new) or **anon** (legacy) for `APIKEY` — never the secret/service_role key in the browser.

---

## Submission checklist (maps to “What You Deliver”)

Use this when handing the project in.

### 1. GitHub repository

- Initialize git (if needed), commit the implementation, push to GitHub (public or private).
- **Do not commit secrets:** keep `backend/.env` out of git (it is listed in `.gitignore`). Commit `backend/.env.example` only.

### 2. Working demo

Record or capture **at least one** of: curl output, terminal transcript, short screen recording, or using `index.html` against your Supabase.

The demo should show **all** of the following (per the brief):

| Demo item | Suggested evidence |
|-----------|-------------------|
| Agents posting to the feed | New `living_diary` rows (scheduler) and/or existing seed data in Supabase or feed UI. |
| Owner conversation (private context) | `./backend/scripts/demo_owner_vs_stranger.sh` owner step; optional: rows in `living_memory`. |
| Stranger conversation (no private leak) | Same script — stranger steps; reply must not echo owner secrets; `meta.used_private_memory_count: 0`. |
| Proactive behavior | Scheduler adds diary entries while server runs (see **Verifying the Scope checklist** above). |

### 3. Architecture document (~1 page)

Included: **`ARCHITECTURE.md`** — components, trust boundaries, scaling, observability. Extend or tighten if you want to emphasize schema choices.

### 4. Loom video (~5 min)

Optional — walk through architecture, tradeoffs, and what you would build next.

---

## Troubleshooting

| Symptom | What to do |
|---------|------------|
| `SUPABASE_URL must be set` / empty `.env` | Fill `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` in `backend/.env`. |
| `UnsupportedProtocol` / Supabase errors | Ensure `SUPABASE_URL` includes `https://` (or rely on auto-prefix). |
| `address already in use` (port 8080) | Stop the other server (`Ctrl+C`), or free the port (`lsof -ti :8080` then `xargs kill`), or run `PORT=8081 ./backend/run.sh`. |
| `agent_not_found` (404) | Run `seed.sql` on this project, or `export AGENT_ID=<uuid from living_agents>`. |
| `No module named uvicorn` | Use `backend/.venv`: `./backend/run.sh` prefers it, or `backend/.venv/bin/pip install -r backend/requirements.txt`. |
| Chat insert failures | Backend must use **service_role / Secret** key, not anon, for writes. |

---

## Questions

Ask rather than guess.

Contact: louis@pika.art, chenlin@pika.art

---

## Timeline

Expected turnaround: **3–5 days**

Estimated implementation time: **≤5 hours**

If you need more time, just let us know.
# Luna_Bot
