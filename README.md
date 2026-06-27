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
 MQTT ──┤  MarketClient ── market_open  ─► run_bidding()  ─► publish orderbook   │
(ASSUME)│               ── market result ─► run_clearing() ─► battery schedule   │
        │  BatteryClient ◄── battery responses                                   │
        │                                                                        │
 HTTP ──┤  /chat ─► Agent.chat() ─► LLM (+ tools, incl. "explain what happened") │
(user)  │  / , /prosumer/* , /pipeline/status , /static                         │
        └────────────────────────────────────────────────────────────────────────┘
```

The **bidding** and **clearing** flows are plain lists of small async steps
(`market/bidding.py`, `market/clearing.py`). Each step records a line in a
*trace*; that trace is what the chat assistant reads back to explain the bid.

All per-agent state lives on one explicit `Agent` object (`agent.py`) — there
are no module globals.

## Project structure

```
src/
  main.py            FastAPI app + startup (builds the Agent, connects MQTT)
  agent.py           the Agent: profile, preferences, LLM, MQTT, pipeline memory
  api.py             all HTTP endpoints
  config.py          one place for all settings and secret-file loading
  prosumer.py        loading the prosumer's profile from disk
  forecasting.py     calling the Chronos forecasting service
  battery_utility.py wrapper around the battery_utility_calculator package
  llm/               chat backends (Mistral / OpenAI / LM Studio), prompt, tools
  market/
    flow.py          shared pipeline machinery (context, trace, live status)
    bidding.py       the market-open pipeline
    clearing.py      the market-clearing pipeline
    mqtt.py          MQTT clients for the market and the battery
  context/           the platform context fed into the chat system prompt
  static/            the web UI (chat + preferences panel + pipeline viewer)
```

## Running

One agent is configured by two environment variables: `PROFILE_ID` (which
prosumer) and `AGENT_ID` (its name on the market).

```bash
cd src
PROFILE_ID=84 AGENT_ID=S_01 uvicorn main:app --port 8002
```

Then open http://localhost:8002 for the chat UI.

To launch the usual set of four agents (two buyers, two sellers) at once, run
`python start_agents.py` from `src/` (or `python launch.py`, which also starts
the Chronos, battery and ASSUME services).

## External dependencies

This agent does not run in isolation — it expects these to be reachable:

- **Chronos forecaster** at `http://127.0.0.1:8000` (see `config.CHRONOS_URL`).
- **An MQTT broker** at `localhost:1883` for the ASSUME market (and the battery,
  unless `config.MQTT_ONLINE` is set).
- **`data/`** (git-ignored): the prosumer profiles, price data and pre-computed
  forecasts. Expected under `src/data/`.
- **Secret files** in `src/` (git-ignored): `mas4te_mistral_api_key.yml`,
  `mas4te_restapi_key.yml`, and — only when `MQTT_ONLINE` is true —
  `mas4tecontroller_mqtt_credentials.yml`.

## Configuration

Everything tunable lives in `src/config.py`: the Chronos URL, which LLM backend
to use (`LLM_BACKEND`), the MQTT brokers (`MQTT_ONLINE` toggles local vs. the
live Jülich broker) and the REST endpoint for battery schedules.
