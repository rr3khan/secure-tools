# 1Password Setup Guide

This guide explains how to set up 1Password for use with the Secure Tool Runner.

## Prerequisites

1. **1Password CLI** - Install with:

   ```bash
   brew install 1password-cli
   ```

   For detailed installation instructions (Windows, Linux, manual install), see the
   [official 1Password CLI guide](https://developer.1password.com/docs/cli/get-started/).

2. **1Password Account**

## Setup Steps

### 1. Sign in to 1Password CLI

For interactive use:

```bash
op signin
```

### 2. Create a Vault

Create a dedicated vault for your secure tools:

```bash
op vault create SecureTools
```

### 3. Add Required Secrets

#### Weather API Key (OpenWeatherMap)

1. **Get a free API key** from [OpenWeatherMap](https://openweathermap.org/api):

   - Sign up at https://home.openweathermap.org/users/sign_up
   - Go to https://home.openweathermap.org/api_keys
   - Copy your API key (it may take a few minutes to activate)

2. **Store it in 1Password**:

```bash
op item create \
  --category="API Credential" \
  --title="WeatherAPI" \
  --vault="SecureTools" \
  api_key="YOUR_ACTUAL_API_KEY_HERE"
```

3. **Test the integration**:

```bash
task demo:live
```

> **Note**: New OpenWeatherMap API keys can take 10-30 minutes to activate.
> If you get a 401 error, wait a bit and try again.

### 4. Verify Setup

Test that you can read the secrets:

```bash
# Should return your API key
op read "op://SecureTools/WeatherAPI/api_key"

```

### 5. Test with the Tool Runner

```bash
python run.py test-onepassword --vault SecureTools
```

## Secret Reference Format

Secrets are referenced using the 1Password URI format:

```
op://<vault>/<item>/<field>
```

Examples:

- `op://SecureTools/WeatherAPI/api_key`
- `op://SecureTools/InternalAPI/auth_token`
- `op://MyVault/DatabaseCreds/password`

## How Secrets Are Configured

Secret references are defined in `secure_tools/tool_configs/tools.yml`, **not** in Python code. Each tool specifies which secrets it needs:

```yaml
# secure_tools/tool_configs/tools.yml
tools:
  get_current_weather:
    description: "Get the current weather for a location."
    executor: "get_current_weather"
    parameters:
      # ... parameter schema ...
    secrets:
      # Supports both env vars and 1Password
      - env: "OPENWEATHER_API_KEY"   # Environment variable (checked first)
        item: "WeatherAPI"            # 1Password item (fallback)
        field: "api_key"
```

### Secret Resolution Order

Secrets are resolved in this order:
1. **Environment variable** (`env`) - if set in environment
2. **1Password CLI** (`item`/`field`) - via `op read op://vault/item/field`

You can configure either or both. If both are set, env var takes priority.

### Using Environment Variables

Environment variables work with:
- **[1Password Environments](https://developer.1password.com/docs/environments/)** - Sync secrets to local `.env` files
- **CI/CD pipelines** - GitHub Actions, GitLab CI, etc.
- **Docker** - Pass secrets via `-e` flag
- **Manual** - `export OPENWEATHER_API_KEY=your-key`

### Using 1Password CLI

The **vault** is specified via CLI:

```bash
python run.py chat --vault SecureTools
```

At runtime, the system combines vault + item + field:
- `op://SecureTools/WeatherAPI/api_key`

This flexibility allows:
- Same config file across environments
- Different secret sources for dev/staging/prod
- Easy auditing of which tools need which secrets

## Security Best Practices

1. **Use a dedicated vault** - Keep AI tool secrets separate from personal credentials
2. **Least privilege** - Only grant access to secrets the tools actually need
3. **Audit access** - Review 1Password audit logs for secret access
4. **Rotate secrets** - Regularly rotate API keys and tokens
5. **Use service accounts** - For automation, use 1Password service accounts with scoped permissions

## Troubleshooting

### "Not signed in"

```bash
op signin
# or
eval $(op signin)
```

### "Vault not found"

```bash
op vault list  # Check available vaults
op vault create SecureTools  # Create if missing
```

### "Item not found"

```bash
op item list --vault SecureTools  # Check items in vault
```

### Permission denied

- Check your 1Password permissions
- For service accounts, verify the token has access to the vault
