# MAS4TE Communication Agent

An autonomous trading agent for the MAS4TE virtual energy storage platform.
Each running process represents one prosumer (a household with solar and/or a
battery). The agent does two things:

1. **Trades automatically.** When the market opens it forecasts the prosumer's
   demand, solar and prices, works out how much storage capacity to bid for and
   at what price, and submits an orderbook. When the market clears it sends the
   resulting battery schedule.
2. **Explains itself.** A chat assistant (LLM) answers the prosumer's questions
   in plain language and can explain exactly what the agent did on their behalf.

## How it works

```
        ┌─────────────────── one agent = one FastAPI process ───────────────────┐
        │                                                                        │
 MQTT ──┤  MarketClient ─┐                                                       │
(ASSUME)│                └─► jobs queue ─► worker thread ─► bidding pipeline     │
        │                                                └─► clearing pipeline   │
        │  BatteryClient ◄── battery responses                                   │
        │                                                                        │
 HTTP ──┤  /chat ─► Agent.chat() ─► LLM (+ tools, incl. "explain what happened") │
(user)  │  / , /prosumer/* , /pipeline/status , /static                          │
        └────────────────────────────────────────────────────────────────────────┘
```

**Threading, in three sentences.** paho gives us an MQTT thread; its callback
must return immediately or the broker drops us for missing keepalives, so the
callback only puts the message on `agent.jobs`. One worker thread takes jobs off
that queue and runs the pipeline. Because there is exactly one worker, two
pipeline runs can never overlap and nothing needs a lock — and there is no
asyncio anywhere in the codebase.

**A pipeline is a list of functions.** Each takes the same `MarketContext`, reads
and writes `ctx.data`, and appends one line to `ctx.trace` saying what it did.
Running one is a for loop (`market/pipeline.py`, ~100 lines including the live
status object). `market/bidding.py` and `market/clearing.py` are each just those
functions plus the list at the bottom, so you can read either file top to bottom
and see everything that happens.

That trace is what the chat assistant reads back to explain a bid, and what the
pipeline viewer shows while a run is in progress.

All per-agent state lives on one explicit `Agent` object (`agent.py`) — there
are no module globals.

## Project structure

```
launch.py            starts and supervises everything; --check reports readiness
agents.toml          which agents exist, on which ports, and where services live
smoke_test.py        run both pipelines once, without broker/ASSUME/Chronos
src/
  main.py            builds the Agent, starts it, mounts the FastAPI app
  agent.py           the Agent: profile, preferences, LLM, MQTT, jobs queue, worker
  api.py             all HTTP endpoints
  config.py          one place for all settings and secret-file loading
  agents_config.py   reads agents.toml
  prosumer.py        loading the prosumer's profile from disk
  forecasting.py     calling the Chronos forecasting service
  llm/               chat backends (Mistral / OpenAI / LM Studio / offline), prompt, tools
  market/
    pipeline.py      MarketContext, PipelineStatus and the for loop that runs steps
    bidding.py       the market-open pipeline, start to finish
    clearing.py      the market-clearing pipeline, start to finish
    mqtt.py          MQTT clients for the market and the battery
    buc_debug.py     opt-in tracing for the optimiser (BUC_DEBUG=1)
    clear_retained.py  wipe retained market_open messages between runs
  context/           the platform context fed into the chat system prompt
  static/            the web UI (chat + preferences panel + pipeline viewer)
```

The Battery Utility Calculator is called directly from `bidding.py` and
`clearing.py`, with its arguments spelled out at the call site. There is no
wrapper module in between.

## Running

### Setup (once)

`battery-utility-calculator` is **not on PyPI**, so `pyproject.toml` points at
its public git repo. Nothing else is needed — no local checkout of the optimiser,
same command on every platform:

```bash
python -m venv .venv
.venv/bin/pip install -e .          # Windows: .venv\Scripts\pip install -e .
```

or, with uv:

```bash
uv venv && uv pip install -e .
```

The pin follows the `main` branch. That is deliberately the only way the
optimiser gets installed: an earlier `[tool.uv.sources]` override silently
replaced it with whatever branch a sibling checkout happened to be on, which is
how a stale optimiser ends up in the venv. To hack on both repos at once,
install the checkout over the pin explicitly and remember you have done so:

```bash
pip install -e ../battery-utility-calculator
```

A branch pin is not reproducible — the next commit on `main` silently changes
your install. For a frozen build, pin the commit instead:
`...battery-utility-calculator@12d9c94a`.

`python launch.py --check` prints which optimiser is installed and where it came
from, so you can see at a glance which of the two you have:

```
Battery Utility Calculator
  version 0.3.0
  pinned to https://github.com/MAS4TE/battery-utility-calculator @ main (12d9c94a)
```

Check that first when the optimiser behaves oddly.

Optional extras: `pip install -e '.[lmstudio]'` for the local LM Studio backend.

### Check the pipelines without any services

```bash
python smoke_test.py --profile 84 --hours 1
```

Builds a real agent, feeds it a made-up market opening and clearing result, and
prints what every step did. Runs with `MAS4TE_DRY_RUN=1`, so nothing is
published, POSTed or sent to the battery. One optimiser solve happens per
candidate volume (per location, for buyers) — keep `--hours` small on a slow
machine.

### Check before you start

```bash
python launch.py --check
```

This reports, without starting anything: whether the dependencies are installed,
whether `src/data/` is in place and every configured profile loads, whether the
MQTT broker is reachable, whether an LLM key is configured, which external
services are present, and whether any agent port is already taken.

### Start

```bash
python launch.py                       # every agent in agents.toml + the services
python launch.py --no-services         # agents only (same as: cd src && python start_agents.py)
python launch.py --agents B_01,S_01    # just these two
```

`agents.toml` at the repo root is the single source of truth for which agents
exist, which port each one gets and where the external services live. Each agent
gets its web UI on its own port (`http://localhost:8002` and up) and its output
in `logs/<AGENT_ID>.log`. Ctrl-C stops the whole tree in order.

**Note:** one agent is one process, and the bidding step runs an optimiser — on a
small machine start two or three (`--agents ...`), not the full roster.

### A single agent by hand

```bash
cd src
PROFILE_ID=84 AGENT_ID=S_01 python -m uvicorn main:app --port 8002
```

Then open http://localhost:8002 for the chat UI.

### When the bidding step seems to hang

```bash
BUC_DEBUG=1 python launch.py --agents B_01        # Windows: set BUC_DEBUG=1
```

Every optimiser solve then reports its volume, location, timestep count, model
size and duration, screens the input series for NaN/inf/duplicate indices, and
on failure reports the real termination condition (infeasible / unbounded / ...)
instead of the bare "A feasible solution was not found".

`BUC_DEBUG=2` additionally streams the HiGHS log, which is the only way to tell a
solver that is grinding from one that never started. `ECC.optimize()` takes no
solver options, so this wrapper accepts them:

```bash
BUC_SOLVER_OPTIONS="time_limit=60"   # an apparent hang becomes a reported status
BUC_SOLVER_OPTIONS="presolve=off"    # skip presolve's dependent-equations search
```

Also run agents with `PYTHONUNBUFFERED=1` on Windows — block-buffered stdout is
easily mistaken for a hung process.

### Between simulation runs

ASSUME publishes `market_open` with the retain flag, so a restarted agent
immediately bids on a window that has already passed. Wipe those:

```bash
cd src && python -m market.clear_retained
```

## External dependencies

This agent does not run in isolation — it expects these to be reachable:

- **Chronos forecaster** at `http://127.0.0.1:8000` (see `config.CHRONOS_URL`).
  Not needed for a window that already has a pre-computed forecast CSV in `data/`.
- **An MQTT broker** at `localhost:1883` for the ASSUME market (and the battery,
  unless `config.MQTT_ONLINE` is set). The agents connect asynchronously and keep
  retrying, so they start fine before the broker does and join when it appears.
- **`data/`** (git-ignored): the prosumer profiles, price data and pre-computed
  forecasts. Expected under `src/data/`, or anywhere you point `MAS4TE_DATA_DIR`.
- **Secret files** in `src/` (git-ignored): `mas4te_mistral_api_key.yml`,
  `mas4te_restapi_key.yml`, and — only when `MQTT_ONLINE` is true —
  `mas4tecontroller_mqtt_credentials.yml`.

## Configuration

Everything tunable lives in `src/config.py`: the Chronos URL, which LLM backend
to use (`LLM_BACKEND`), the MQTT brokers (`MQTT_ONLINE` toggles local vs. the
live Jülich broker) and the REST endpoint for battery schedules.

Most of it can be overridden from the environment without editing the file:
`MAS4TE_DATA_DIR`, `CHRONOS_URL`, `LLM_BACKEND`, `MQTT_ONLINE`,
`MQTT_LOCAL_BROKER`, `MQTT_LOCAL_PORT`, `BUC_SOLVER`, `MAS4TE_DRY_RUN`, plus the
per-agent `PROFILE_ID` and `AGENT_ID`.

`BUC_SOLVER` defaults to `appsi_highs`. The BUC's own default is `gurobi`, which
we have no licence for, so every call site passes this setting explicitly.
`MAS4TE_DRY_RUN=1` computes everything but sends nothing outward.

`LLM_BACKEND` defaults to `auto`: it uses Mistral when a key is configured
(`src/mas4te_mistral_api_key.yml` or `MISTRAL_API_KEY`) and otherwise falls back
to an offline backend that answers from the agent's own data. A missing key
never stops an agent from trading — only the chat quality suffers.
