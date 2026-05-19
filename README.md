# Emblem AI

Personal Hermes agent for Adam McBride. Powered by Emblem Vault.

A self-improving agent with persistent memory, multi-chain crypto operations, portfolio tracking, automated workflows, and multi-platform messaging. Built on Nous Research's Hermes agent framework with Emblem Vault integration for 200+ trading tools across 7 blockchains.

## What it does

- **Crypto operations** — swap, bridge, and manage tokens across Solana, Ethereum, Base, BSC, Polygon, Hedera, and Bitcoin via Emblem Vault.
- **Portfolio tracking** — automated snapshots, P&L tracking, allocation drift alerts, and daily performance summaries.
- **Persistent memory** — SQLite-backed memory with full-text search. Remembers preferences, facts, and conversation context across sessions.
- **Scheduled automations** — morning briefings, portfolio checks every 4 hours, news digests, and memory nudges run unattended.
- **Multi-platform** — CLI, Telegram, Discord. Start on one, pick up on another.
- **Research** — token lookup, market overview, safety checks, and news aggregation.
- **Task management** — notes, to-dos, reminders, and daily briefings.
- **Self-improving** — auto-memorizes important interactions, builds behavioral patterns over time.

## Quick start

```bash
git clone https://github.com/Adam-McBride/Emblem-AI.git
cd Emblem-AI
pip install -e .
cp .env.example .env
# Fill in your API keys in .env
python emblem_ai.py
```

## Configuration

Copy `.env.example` to `.env` and set:

- `OPENROUTER_API_KEY` — LLM provider key (OpenRouter, OpenAI, or Anthropic).
- `EMBLEM_API_KEY` — Emblem Vault API key for crypto operations.
- `EMBLEM_WALLET_PASSWORD` — wallet password for transaction signing.
- `TELEGRAM_BOT_TOKEN` — optional, for Telegram gateway.
- `DISCORD_BOT_TOKEN` — optional, for Discord gateway.

## Architecture

```
emblem_ai.py (entry point)
├── config/
│   ├── agent_config.py  — environment and config loading
│   └── persona.py       — personality and behavioral traits
├── skills/
│   ├── crypto/
│   │   ├── wallet.py    — multi-chain wallet via Emblem Vault
│   │   ├── trading.py   — swaps, limit orders, trade management
│   │   └── bridge.py    — cross-chain bridging
│   ├── portfolio/
│   │   └── tracker.py   — snapshots, P&L, allocation alerts
│   ├── research/
│   │   └── market.py    — token lookup, news, safety checks
│   ├── assistant/
│   │   └── tasks.py     — notes, to-dos, daily briefings
│   └── scheduling/
│       └── scheduler.py — cron automations
├── memory/
│   └── store.py         — SQLite + FTS5 persistent memory
├── gateway/
│   └── adapters.py      — CLI, Telegram, Discord adapters
├── workflows/
│   └── automations.py   — multi-step automated workflows
└── tools/
    └── llm_client.py    — multi-provider LLM client
```

## Persona

The agent uses a defined persona with:
- Behavioral traits (direct, proactive, cautious with money, crypto-native).
- Boundaries (never share keys, always confirm large trades, no financial advice).
- Proactive behaviors (alert on portfolio changes, flag gas spikes, summarize overnight activity).

## Scheduled automations

| Job | Schedule | Description |
|-----|----------|-------------|
| portfolio_check | Every 4 hours | Snapshot balances and check alerts |
| morning_briefing | 8 AM daily | Portfolio + tasks + market + news |
| news_digest | Noon and 6 PM | Aggregate crypto news |
| alert_check | Every 15 min | Check for portfolio alerts |
| memory_nudge | Every 30 min | Auto-memorize important context |

## Links

- X: [@EmblemAI_](https://x.com/EmblemAI_)
- Builder: [@adamamcbride](https://x.com/adamamcbride)
- Powered by: [Emblem Vault](https://x.com/EmblemVault)

## License

MIT
