# Architecture

## Agent Loop

1. Message arrives from a platform (CLI, Telegram, Discord).
2. Gateway normalizes it into an IncomingMessage.
3. Agent stores the message in conversation history.
4. Memory retrieves relevant past context via FTS5 search.
5. System prompt is built from persona + memory context.
6. LLM generates a response via the configured provider.
7. Response is stored in conversation history.
8. Auto-memorize checks if anything important should be persisted.
9. OutgoingMessage is sent back to the platform.

## Subsystems

Each subsystem is independent and testable:

- **Config** loads from environment and validates.
- **Persona** builds the system prompt from traits and boundaries.
- **Memory** handles persistence with SQLite + FTS5 full-text search.
- **Gateway** normalizes messages across platforms.
- **Skills** provide domain-specific capabilities.
- **Workflows** chain skills into multi-step automations.
- **Scheduler** triggers workflows on cron schedules.
- **LLM Client** handles provider-agnostic completions.

## Transaction Safety

The agent has two safety thresholds for crypto operations:
- auto_approve_below ($10): small transactions execute without confirmation.
- require_confirmation_above ($100): large transactions always require explicit approval.

Transactions between $10-$100 proceed normally but are logged.

The agent never has access to private keys directly — all signing goes through Emblem Vault's authenticated API.
