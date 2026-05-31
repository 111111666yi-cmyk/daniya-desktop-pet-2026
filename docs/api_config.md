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

## Safety Rules

- Do not paste API Keys into Git-tracked files.
- Do not share full `.env` files in issues.
- Screenshots and logs must be desensitized before sharing.
