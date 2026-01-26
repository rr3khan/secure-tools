# Quick Start Guide

Get the Secure Tool Runner up and running in 5 minutes.

## Prerequisites

- Python 3.11+
- Ollama running locally with `llama3.1:8b` or any other [tool supported model](https://ollama.com/blog/tool-support)
- 1Password CLI (optional for testing)

## Installation (One Command)

First, install [Task](https://taskfile.dev/installation/):

```bash
brew install go-task
```

Then set up the project:

```bash
cd secure-tools
task setup
```

<details>
<summary>Manual installation (if Task isn't available)</summary>

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

</details>

## Quick Test (No 1Password Required)

The tool runner works in mock mode without 1Password, perfect for testing:

```bash
# Verify everything is working
task check

# Run a demo query
task demo

# Start interactive chat
task chat
```

Or with Python directly:

```bash
source venv/bin/activate
python run.py chat
```

Try these prompts:

- "What's the weather in Paris?"
- "Check the status of project X"
- "What services are available?"

4. Test 1Password connection:

   ```bash
   python run.py test-onepassword
   ```

5. Chat with real authentication:
   ```bash
   python run.py chat --vault SecureTools
   ```

## Commands

### Using Task (Recommended)

```bash
task setup           # One-time setup
task chat            # Interactive chat
task demo            # Run demo query (mock data)
task demo:live       # Test real API with 1Password secret
task test            # Run tests
task check           # Verify connections
task tools           # List available tools
task clean           # Remove venv and caches
```

### Using Python Directly

```bash
source venv/bin/activate

python run.py chat                              # Interactive chat
python run.py chat --single "Weather in Tokyo?" # Single query
python run.py chat --model llama3.1:8b          # Specify model
python run.py test-connection                   # Test Ollama
python run.py test-onepassword                  # Test 1Password
python run.py list-tools                        # List tools
```

## What's Happening Under the Hood

1. **You type a message** → Orchestrator receives it
2. **Orchestrator → Ollama** → Sends message with tool definitions
3. **Ollama decides** → Requests `get_current_weather` tool
4. **Orchestrator validates** → Checks tool is allowed, params are valid
5. **Secrets Broker fetches** → Gets API key from 1Password
6. **Secrets Broker executes** → Calls weather API with key
7. **Secrets Broker scrubs** → Removes any leaked secrets from response
8. **Orchestrator → Ollama** → Sends sanitized result
9. **Ollama responds** → Generates natural language answer
10. **You see the result** → Secrets never exposed to the LLM

## Tool Configuration

Tools are defined in `secure_tools/tool_configs/tools.yml`, not in Python code. This makes it easy to add or modify tools without changing code.

```yaml
# secure_tools/tool_configs/tools.yml
tools:
  get_current_weather:
    description: "Get the current weather for a location."
    executor: "get_current_weather"
    parameters:
      type: object
      properties:
        location:
          type: string
          description: "The location to get weather for"
      required: ["location"]
    secrets:
      - item: "WeatherAPI"      # 1Password item name
        field: "api_key"        # Field within the item
```

The **vault** is specified via CLI (`--vault SecureTools`), and combined with `item` and `field` to create the full 1Password reference: `op://SecureTools/WeatherAPI/api_key`

## Next Steps

- See `docs/1password-setup.md` for detailed 1Password configuration
- Read the architecture in `README.md`
- Add your own tools - see [Adding New Tools](#adding-new-tools) below

## Adding New Tools

1. **Create the executor** in `secure_tools/tools/executors.py`:

```python
def execute_my_new_tool(arguments: dict, secrets: dict) -> ToolResult:
    api_key = secrets.get("api_key")
    # ... your tool logic ...
    return ToolResult(success=True, content=json.dumps(result))
```

2. **Register the executor** in `TOOL_EXECUTORS` dict (same file):

```python
TOOL_EXECUTORS = {
    # ... existing tools ...
    "my_new_tool": execute_my_new_tool,
}
```

3. **Add config** to `secure_tools/tool_configs/tools.yml`:

```yaml
  my_new_tool:
    description: "What this tool does"
    executor: "my_new_tool"
    parameters:
      type: object
      properties:
        # ... your parameters ...
      required: []
    secrets:
      - item: "MyAPICredential"
        field: "api_key"
```

4. **Add the secret** to 1Password:

```bash
op item create --category="API Credential" \
  --title="MyAPICredential" --vault="SecureTools" \
  api_key="your-api-key"
```

That's it! No changes needed to setup.py or other files.
