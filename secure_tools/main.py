"""
Secure Tool Runner - Main Entry Point

A secure tool access layer between Ollama LLMs and authenticated services.
"""

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

from .config import config
from .orchestrator import Orchestrator
from .secrets_broker import SecretsBroker
from .tools.setup import setup_tools

app = typer.Typer(
    name="secure-tools", help="Secure Tool Runner - Secure LLM tool execution with 1Password"
)
console = Console()


def create_orchestrator(vault: str = "SecureTools", require_secrets: bool = False) -> Orchestrator:
    """Create and configure the orchestrator with all components."""
    # Create the secrets broker (trusted boundary)
    broker = SecretsBroker(require_secrets=require_secrets)

    # Register tools with their secret requirements
    setup_tools(broker, vault=vault)

    # Create the orchestrator (LLM-facing, untrusted)
    orchestrator = Orchestrator(broker)

    return orchestrator


@app.command()
def chat(
    vault: str = typer.Option(
        "SecureTools", "--vault", "-v", help="1Password vault name containing secrets"
    ),
    model: str = typer.Option("llama3.1:8b", "--model", "-m", help="Ollama model to use"),
    single: str | None = typer.Option(
        None, "--single", "-s", help="Single message mode - send one message and exit"
    ),
    live: bool = typer.Option(
        False, "--live", "-l", help="Require real secrets from 1Password (no mock fallback)"
    ),
    seed: int | None = typer.Option(
        None, "--seed", help="Random seed for reproducible outputs (same seed = same response)"
    ),
):
    """
    Start an interactive chat session with tool support.

    The LLM can request tools that require authentication.
    Secrets are fetched from 1Password and never exposed to the model.

    Use --live to require real 1Password secrets (fails if unavailable).
    """
    # Update config
    config.ollama.model = model
    config.ollama.seed = seed
    config.onepassword.vault = vault

    mode_label = "[green]LIVE[/green]" if live else "[yellow]MOCK[/yellow]"
    seed_label = f"[cyan]{seed}[/cyan]" if seed is not None else "[dim]random[/dim]"
    console.print(
        Panel.fit(
            "[bold cyan]Secure Tool Runner[/bold cyan]\n"
            f"Model: {model} | Vault: {vault} | Mode: {mode_label} | Seed: {seed_label}\n"
            "[dim]Type 'exit' or 'quit' to end the session[/dim]",
            border_style="cyan",
        )
    )

    console.print()
    if live:
        console.print("[green]🔐 Live mode: Using real secrets from 1Password[/green]")
    else:
        console.print(
            "[dim]Security: LLM never sees credentials. Auth handled by Secrets Broker.[/dim]"
        )
    console.print()

    try:
        orchestrator = create_orchestrator(vault=vault, require_secrets=live)
    except Exception as e:
        console.print(f"[red]Failed to initialize: {e}[/red]")
        raise typer.Exit(1)

    # Single message mode
    if single:
        try:
            response = orchestrator.chat(single)
            console.print(Panel(Markdown(response), title="Assistant", border_style="green"))
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1)
        return

    # Interactive mode
    while True:
        try:
            user_input = Prompt.ask("\n[bold blue]You[/bold blue]")

            if user_input.lower() in ("exit", "quit", "q"):
                console.print("[dim]Goodbye![/dim]")
                break

            if user_input.lower() == "reset":
                orchestrator.reset()
                console.print("[dim]Conversation reset.[/dim]")
                continue

            if not user_input.strip():
                continue

            # Process the message
            with console.status("[bold cyan]Thinking...[/bold cyan]"):
                response = orchestrator.chat(user_input)

            console.print()
            console.print(Panel(Markdown(response), title="Assistant", border_style="green"))

        except KeyboardInterrupt:
            console.print("\n[dim]Interrupted. Goodbye![/dim]")
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            console.print("[dim]Use 'reset' to start a new conversation.[/dim]")


@app.command()
def test_connection():
    """Test connection to Ollama."""
    import httpx

    console.print(f"Testing connection to Ollama at {config.ollama.base_url}...")

    try:
        with httpx.Client(timeout=10) as client:
            response = client.get(f"{config.ollama.base_url}/api/tags")
            response.raise_for_status()
            data = response.json()

            models = [m["name"] for m in data.get("models", [])]

            console.print("[green]✓ Connected to Ollama[/green]")
            console.print(f"Available models: {', '.join(models) or 'none'}")

            if config.ollama.model not in models and f"{config.ollama.model}:latest" not in models:
                console.print(
                    f"[yellow]⚠ Configured model '{config.ollama.model}' not found[/yellow]"
                )
            else:
                console.print(f"[green]✓ Model '{config.ollama.model}' available[/green]")

    except Exception as e:
        console.print(f"[red]✗ Failed to connect: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def test_onepassword(
    vault: str = typer.Option("SecureTools", "--vault", "-v", help="Vault name to test"),
):
    """Test connection to 1Password CLI."""
    import subprocess

    console.print("Testing 1Password CLI...")

    try:
        # Check if op is installed
        result = subprocess.run(["op", "--version"], capture_output=True, text=True, timeout=10)

        if result.returncode != 0:
            console.print("[red]✗ 1Password CLI not working[/red]")
            raise typer.Exit(1)

        console.print(f"[green]✓ 1Password CLI version: {result.stdout.strip()}[/green]")

        # Check if we can list vaults
        result = subprocess.run(
            ["op", "vault", "list", "--format=json"], capture_output=True, text=True, timeout=30
        )

        if result.returncode != 0:
            console.print("[yellow]⚠ Not signed in to 1Password[/yellow]")
            console.print("[dim]Run 'op signin' or set OP_SERVICE_ACCOUNT_TOKEN[/dim]")
        else:
            import json

            vaults = json.loads(result.stdout)
            vault_names = [v["name"] for v in vaults]

            console.print("[green]✓ Signed in to 1Password[/green]")
            console.print(f"Available vaults: {', '.join(vault_names)}")

            if vault not in vault_names:
                console.print(f"[yellow]⚠ Vault '{vault}' not found[/yellow]")
            else:
                console.print(f"[green]✓ Vault '{vault}' available[/green]")

    except FileNotFoundError:
        console.print("[red]✗ 1Password CLI not installed[/red]")
        console.print("[dim]Install with: brew install 1password-cli[/dim]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def list_tools():
    """List available tools and their requirements."""
    from .tools import tool_registry

    console.print(Panel.fit("[bold]Available Tools[/bold]", border_style="cyan"))
    console.print()

    for name, tool in tool_registry.items():
        console.print(f"[bold cyan]{name}[/bold cyan]")
        console.print(f"  {tool.description}")

        params = tool.parameters.get("properties", {})
        required = tool.parameters.get("required", [])

        if params:
            console.print("  [dim]Parameters:[/dim]")
            for pname, pinfo in params.items():
                req = "[required]" if pname in required else "[optional]"
                console.print(f"    • {pname}: {pinfo.get('description', 'No description')} {req}")

        console.print()


@app.command()
def test_weather_api(
    location: str = typer.Option("Paris", "--location", "-l", help="Location to get weather for"),
    vault: str = typer.Option("SecureTools", "--vault", "-v", help="1Password vault name"),
):
    """
    Test the real OpenWeatherMap API using a key from 1Password.

    This bypasses the LLM and directly tests the 1Password → API integration.
    Requires: op://SecureTools/WeatherAPI/api_key to be set in 1Password.
    """
    import subprocess

    import httpx

    console.print(
        Panel.fit(
            "[bold cyan]Testing Real Weather API[/bold cyan]\n"
            f"Location: {location} | Vault: {vault}",
            border_style="cyan",
        )
    )
    console.print()

    # Step 1: Fetch API key from 1Password
    console.print("[dim]Step 1: Fetching API key from 1Password...[/dim]")
    secret_ref = f"op://{vault}/WeatherAPI/api_key"

    try:
        result = subprocess.run(
            ["op", "read", secret_ref], capture_output=True, text=True, timeout=30
        )

        if result.returncode != 0:
            console.print(f"[red]✗ Failed to read secret: {result.stderr.strip()}[/red]")
            console.print()
            console.print("[yellow]To fix this, create the secret in 1Password:[/yellow]")
            cmd = 'op item create --category="API Credential" --title="WeatherAPI"'
            cmd += f' --vault="{vault}" api_key="YOUR_KEY"'
            console.print(f"[dim]{cmd}[/dim]")
            console.print()
            console.print("[dim]Get a free API key at: https://openweathermap.org/api[/dim]")
            raise typer.Exit(1)

        api_key = result.stdout.strip()
        # Show only first/last 4 chars for verification
        masked_key = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "****"
        console.print(f"[green]✓ API key retrieved: {masked_key}[/green]")

    except FileNotFoundError:
        console.print("[red]✗ 1Password CLI not installed[/red]")
        raise typer.Exit(1)
    except subprocess.TimeoutExpired:
        console.print("[red]✗ 1Password CLI timed out[/red]")
        raise typer.Exit(1)

    # Step 2: Call OpenWeatherMap API
    console.print()
    console.print("[dim]Step 2: Calling OpenWeatherMap API...[/dim]")

    try:
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {"q": location, "appid": api_key, "units": "metric"}

        with httpx.Client(timeout=10) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        console.print("[green]✓ API call successful![/green]")
        console.print()

        # Display weather data
        weather_info = {
            "location": data.get("name", location),
            "country": data.get("sys", {}).get("country", "Unknown"),
            "temperature": f"{data['main']['temp']}°C",
            "feels_like": f"{data['main']['feels_like']}°C",
            "condition": data["weather"][0]["description"],
            "humidity": f"{data['main']['humidity']}%",
            "wind": f"{data.get('wind', {}).get('speed', 0)} m/s",
        }

        loc = weather_info["location"]
        country = weather_info["country"]
        temp = weather_info["temperature"]
        feels = weather_info["feels_like"]
        panel_content = (
            f"[bold]{loc}, {country}[/bold]\n\n"
            f"🌡️  Temperature: {temp} (feels like {feels})\n"
            f"☁️  Condition: {weather_info['condition']}\n"
            f"💧 Humidity: {weather_info['humidity']}\n"
            f"💨 Wind: {weather_info['wind']}"
        )
        console.print(Panel(panel_content, title="Live Weather Data", border_style="green"))

        console.print()
        console.print("[green]✓ Full integration test passed![/green]")
        console.print(
            "[dim]The API key was fetched from 1Password and used to call the real API.[/dim]"
        )
        console.print("[dim]The LLM will now be able to use this tool with real data.[/dim]")

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            console.print("[red]✗ API key is invalid (401 Unauthorized)[/red]")
            console.print("[dim]Check your OpenWeatherMap API key in 1Password[/dim]")
        elif e.response.status_code == 404:
            console.print(f"[red]✗ Location '{location}' not found[/red]")
        else:
            console.print(f"[red]✗ API error: {e.response.status_code}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]✗ Error calling API: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def help():
    """Show a comprehensive guide on how to use Secure Tools."""
    help_text = """
# Secure Tools - Quick Reference

## What is this?
A secure tool access layer between Ollama LLMs and authenticated APIs.
Secrets are stored in 1Password and **never exposed to the LLM**.

## Getting Started

1. **Start a chat session:**
   ```
   task chat
   ```

2. **Use real API keys from 1Password:**
   ```
   task chat:live
   ```

3. **Single query (no interactive mode):**
   ```
   task demo
   ```

## Available Commands

| Command               | Description                              |
|-----------------------|------------------------------------------|
| `task chat`           | Interactive chat with mock data          |
| `task chat:live`      | Interactive chat with real 1Password secrets |
| `task demo`           | Quick demo query                         |
| `task test`           | Run tests                                |
| `task check`          | Verify Ollama & 1Password connections    |
| `task lint`           | Run linter                               |
| `task ci`             | Run all CI checks                        |

## CLI Options

```
python run.py chat --help          # See all chat options
python run.py chat --live          # Require real secrets
python run.py chat --model qwen2   # Use different model
python run.py chat --single "..."  # Single message mode
python run.py chat --seed 42       # Reproducible outputs (same seed = same response for same input)
```

## Setting Up 1Password

1. Install 1Password CLI: `brew install 1password-cli`
2. Sign in: `op signin`
3. Create a vault: `op vault create SecureTools`
4. Add your API keys to the vault

See `docs/1password-setup.md` for detailed instructions.

## Architecture

```
User → LLM → Orchestrator → SecretsBroker → 1Password
                                  ↓
                            Tool Executor → External API
```

The LLM **never sees secrets**. The SecretsBroker is the trusted boundary.
"""
    console.print(Markdown(help_text))


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
