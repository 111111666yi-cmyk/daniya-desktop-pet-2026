# API Configuration

## No-Key Mode

Daniya can run without an API Key. If no valid key is available, local fallback should keep the UI usable.

## First-Run Wizard

The first-run wizard can skip API setup or save:

- Provider
- Base URL
- Model
- API Key

API Key values are written to the local `.env` file and are not committed to Git.

## Settings Center

Open the right-click menu, then open Settings Center. Use the model/API section to change providers, test connection, save settings, or clear the current Key.

## OpenAI-Compatible Providers

For providers such as Zhipu, Kimi, or Doubao, use the provider's OpenAI-compatible Base URL, model name, and API Key. Exact availability depends on the provider account, quota, and network.

### Xiaomi MiMo

MiMo uses an OpenAI-compatible chat endpoint, but it needs an `api-key` auth header instead of the default Bearer header.

Recommended settings:

```text
Provider: OpenAI-compatible
Base URL: https://api.xiaomimimo.com/v1
Model: mimo-v2.5
Auth Header: api-key
API Key Env: OPENAI_COMPATIBLE_API_KEY
```

In the first-run wizard, enter the MiMo Base URL and model under `OpenAI-compatible`; the app normalizes `xiaomimimo.com` profiles to `Auth Header: api-key` when saving.

Do not mark a Bearer-auth MiMo request as passing if it returns HTTP 200 with empty content. That response is malformed for this app and should fall back safely.

## Safety Rules

- Do not paste API Keys into Git-tracked files.
- Do not share full `.env` files in issues.
- Screenshots and logs must be desensitized before sharing.
