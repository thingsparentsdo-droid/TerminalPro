# TerminalPro
A Python desktop terminal with built-in utilities, fuzzy command suggestions, and Windows Command Prompt and PowerShell support.

## To Use Just Download, Unzip, and Move TermainalPro.exe To Desktop And/Or Pin To Taskbar


TerminalPro is a Python-based terminal-style desktop app with a PyQt6 interface. It combines a command prompt experience with built-in helper commands, user account management, and shell execution for Windows environments.

## Features

- User sign-up and login flow with local account storage
- Terminal-style command input and output window
- Command suggestions while typing
- Built-in helper commands for common tasks, including:
  - `/ping` and `/ping: ...` for network checks
  - `cd ...` for changing directories
  - `hash:` and `hashtext:` for hashing files or text
  - `httpget:` for simple HTTP GET requests
  - `/download ...` for saving remote files locally
  - `randint:`, `randnum:`, and `randrange:` for random values
  - `choice:` for random selection from a list
  - `/sleep` and `/wait` for timed delays
  - `clear` and `cls` to clear output
- Execution of PowerShell commands when the command matches supported PowerShell names
- Native shell execution fallback for general terminal commands

## Project structure

- `main.py` — application entry point and login flow
- `Gui.py` — Qt interface and interactive terminal UI
- `Logic.py` — command processing, authentication, networking, and utilities
- `command_suggestions.json` — autocomplete suggestions for terminal commands
- `userData.json` — persisted local user data created at runtime
- `requirements-build.txt` — packages used for packaging with PyInstaller

## Requirements

Install the dependencies with:

```bash
pip install -r requirements.txt
```

The project also includes PyInstaller for packaging:

```bash
pip install -r TerminalPro/requirements-build.txt
```

## Running the app

From the project directory:

```bash
cd "C:\path\to\TerminalPro"
python main.py
```

If you are outside the folder, use:

```bash
python "C:\path\to\TerminalPro\main.py"
```

## Example usage

Once the app starts, you can:

- create an account by entering `signup` at the username prompt
- log in with an existing account
- use commands such as:

```text
/ping google.com
hash: C:\path\to\file.txt
hashtext: hello world
httpget: https://example.com
/download https://example.com/file.txt
randint: 1,10
choice: red,blue,green
/sleep 5
```

## Notes

- User data is stored in the local app data directory for the current Windows user, under `TerminalPro\userData.json`.
- The app is designed for Windows, including PowerShell execution and interactive terminal behavior.
- Some features rely on external packages such as `PyQt6`, `requests`, `yfinance`, `scikit-learn`, and `gTTS`.

## License

GNU General Public License v3.0
