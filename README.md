# Secure Tool Runner (Ollama + 1Password)

### 🎬 Demo

https://github.com/user-attachments/assets/YOUR_VIDEO_ID

---

## Overview

This project demonstrates a **Secure agent execution pattern** for local LLMs using **Ollama** and **1Password**.

The core idea is simple:

> An LLM can decide _what_ action to take, but it must never see or handle secrets required to perform that action.

Instead, all authentication and secret handling is delegated to a **trusted execution boundary**, ensuring that:

- credentials are never exposed to the model,
- prompt injection cannot exfiltrate secrets,
- and sensitive operations remain auditable and constrained.

---

## Key Goals

- ✅ Allow an LLM to **request actions via tool calling**
- ✅ Authenticate actions using **1Password-managed secrets**
- ✅ Ensure the **LLM never sees credentials**
- ✅ Run entirely **locally** (no cloud LLM API keys)
- ✅ Be simple enough to reason about, test, and extend

---

## High-Level Architecture

At a high level, the system is split into **three trust zones**:

```
[ User ]
   |
   v
[ Orchestrator ]  (LLM-facing, untrusted)
   |
   v
[ Secrets Broker ]  (trusted boundary)
   |
   v
[ 1Password ] -> [ Protected System ]


┌─────────────────────────────────────────────────────────────────┐
│                        UNTRUSTED ZONE                           │
│  ┌──────────┐      ┌──────────────┐      ┌───────────────────┐  │
│  │   User   │ ──── │ Orchestrator │ ──── │  Ollama (LLM)     │  │
│  └──────────┘      └──────────────┘      │  Model            │  │
│                           │              └───────────────────┘  │
└───────────────────────────│─────────────────────────────────────┘
                            │
                    ════════════════════  (Trust Boundary)
                            │
┌───────────────────────────│─────────────────────────────────────┐
│                        TRUSTED ZONE                             │
│                    ┌──────────────┐                             │
│                    │   Secrets    │                             │
│                    │   Broker     │                             │
│                    └──────────────┘                             │
│                           │                                     │
│              ┌────────────┴────────────┐                        │
│              ▼                         ▼                        │
│        ┌──────────┐              ┌───────────┐                  │
│        │ 1Password│              │ Tool APIs │                  │
│        │   CLI    │              │(e.g. Weather)                │
│        └──────────┘              └───────────┘                  │
└─────────────────────────────────────────────────────────────────┘
```

### Trust boundaries matter

- **Untrusted:** user input, LLM output, tool decisions
- **Trusted:** secret retrieval, authentication, external execution

The LLM is _never_ allowed to cross into the trusted zone.

---

## Core Components

### 1. Orchestrator (LLM-facing)

**Responsibilities**

- Sends user prompts to Ollama
- Provides a strict list of allowed tools
- Parses tool calls returned by the model
- Validates tool names and arguments
- Delegates execution to the Secrets Broker
- Sends sanitized tool results back to the LLM

**Important constraints**

- ❌ Does not store secrets
- ❌ Does not talk to 1Password
- ❌ Does not call protected systems directly

Think of the orchestrator as **decision glue**, not execution logic.

---

### 2. Ollama (Local LLM)

- Runs locally via Ollama
- Receives tool definitions
- Decides _when_ a tool should be called
- Generates final user-facing responses

The model:

- **Can** request tools
- **Cannot** authenticate
- **Cannot** access secrets
- **Cannot** bypass policies enforced outside the model

---

### 3. Secrets Broker (Trusted Execution Boundary)

**Responsibilities**

- Holds access to 1Password (via service account)
- Resolves secret references securely
- Executes authenticated actions
- Scrubs outputs to prevent leakage
- Returns only safe, minimal results

This is the **only component** allowed to touch secrets.

---

### 4. 1Password (Secret Store)

- Stores credentials in a dedicated vault
- Accessed via a service account
- Secrets are referenced (not hardcoded)
- Secrets are never returned to the LLM

---

## End-to-End Flow

### Happy Path

1. **User** submits a request

   > “Check the protected status for project X.”

2. **Orchestrator → Ollama**

   - Sends prompt + tool definitions

3. **Ollama → Orchestrator**

   - Returns a `tool_call`:

     ```json
     {
       "name": "get_protected_status",
       "arguments": { "project": "X" }
     }
     ```

4. **Orchestrator → Secrets Broker**

   - Validates tool + args
   - Requests execution

5. **Secrets Broker → 1Password**

   - Retrieves required credential securely

6. **Secrets Broker → Protected System**

   - Performs authenticated request

7. **Secrets Broker → Orchestrator**

   - Returns sanitized result (no secrets)

8. **Orchestrator → Ollama**

   - Sends tool result message

9. **Ollama → User**

   - Produces final natural-language response

✅ The secret was used
✅ The LLM never saw it

---

## Security Model

### What this system guarantees

- **LLM never receives secrets**
- **Secrets are not logged**
- **Tool execution is allow-listed**
- **Prompt injection cannot exfiltrate credentials**
- **Authentication is separated from reasoning**

### Why this is safe

- The LLM only outputs _intent_
- Execution happens behind a hard boundary
- All sensitive operations are centralized and auditable
- Even a compromised model cannot leak secrets it never had

---

## Why This Pattern Exists

LLMs are powerful, but:

- they are not trusted execution environments,
- they are vulnerable to prompt injection,
- and they should not handle credentials.

This project demonstrates a **secure-by-design** alternative:

> _Let models reason, not authenticate._

This pattern is applicable to:

- AI agents
- internal automation
- DevOps tooling
- security workflows
- AI-assisted developer tools

---

## Non-Goals (for this MVP)

To keep the project focused, this MVP intentionally does **not**:

- expose multiple tools
- support arbitrary external APIs
- implement full authorization policies
- deploy to production infrastructure

These can be layered on **after** the core Secure flow is proven.

---

## Future Extensions

Once the MVP is validated, this project can be extended with:

- multiple tools and scoped permissions
- a policy engine for tool access
- a full security regression suite
- SDK-based 1Password integration
- production hardening (rate limits, metrics, tracing)

---

## Summary

This project shows how to safely combine:

- **local LLMs (Ollama)**
- **secure secret management (1Password)**
- **agentic workflows**
- **strong security boundaries**

without ever exposing credentials to the model.

It is a practical example of **Security for AI** and **AI for Security** principles applied to real systems.

---

---

## Quick Start

Install [Task](https://taskfile.dev/) and run setup:

```bash
brew install go-task
task setup
```

Start chatting:

```bash
task chat
```

Or run a demo:

```bash
task demo
```

All available commands:

```bash
task setup           # Create venv & install deps
task chat            # Interactive chat session
task demo            # Demo query (mock data)
task demo:live       # Test real API with 1Password
task test            # Run all tests
task check           # Verify Ollama & 1Password
task tools           # List available tools
task clean           # Clean up
```

### Example Session

```
$ python run.py chat --single "What is the weather today in Tokyo?"

╭──────────────────────────────────────────╮
│ Secure Tool Runner                   │
│ Model: llama3.1:8b | Vault: SecureTools  │
╰──────────────────────────────────────────╯

🔧 Tool call: get_current_weather({'format': 'celsius', 'location': 'Tokyo'})
✅ Tool result: 98 chars

╭───────────────────────────────── Assistant ──────────────────────────────────╮
│ The current weather in Tokyo is 18°C with sunny conditions.                 │
╰──────────────────────────────────────────────────────────────────────────────╯
```

---

## Project Structure

```
secure-tools/
├── run.py                    # CLI entry point
├── requirements.txt          # Dependencies
├── pyproject.toml           # Package configuration
├── secure_tools/
│   ├── __init__.py
│   ├── config.py            # Configuration management
│   ├── orchestrator.py      # LLM-facing component (untrusted)
│   ├── secrets_broker.py    # Trusted execution boundary
│   ├── main.py              # CLI commands
│   └── tools/
│       ├── __init__.py      # Tool registry & definitions
│       ├── executors.py     # Tool implementations
│       └── setup.py         # Tool registration
├── tests/                   # Test suite
└── docs/
    ├── quickstart.md        # Getting started guide
    └── 1password-setup.md   # 1Password configuration
```

---

## With 1Password (Production Mode)

1. Install 1Password CLI: `brew install 1password-cli`
2. Sign in: `op signin`
3. Create vault and secrets:
   ```bash
   op vault create SecureTools
   op item create --category=api_credential \
     --title="WeatherAPI" --vault="SecureTools" \
     api_key="your-openweathermap-key"
   ```
4. Run with real secrets: `python run.py chat`

See `docs/1password-setup.md` for detailed instructions.
