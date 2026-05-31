# Installation

## Downloaded Windows Package

1. Download `DaniyaSummerPet-v0.60-win-x64.zip`.
2. Extract it to a normal folder such as Desktop, Downloads, or another drive.
3. Run `DaniyaSummerPet.exe`.
4. Runtime data is stored in `%APPDATA%\DaniyaSummerPet\`, not beside the exe.

No API Key is required for first launch. The app can use local fallback until a provider is configured.

## Source Checkout

```bat
git clone https://github.com/111111666yi-cmyk/daniya-desktop-pet-2026.git
cd daniya-desktop-pet-2026
install.bat
```

Manual setup:

```bat
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe main.py
```

## Local Runtime Data

Source mode writes ignored runtime data under `data/`. Packaged Windows mode writes to `%APPDATA%\DaniyaSummerPet\`.

Do not commit `.env`, `data/`, `assets/private/`, `models/`, `backups/`, `release/`, `dist/`, or `build/`.
