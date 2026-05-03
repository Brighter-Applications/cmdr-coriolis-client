# cmdr-coriolis-client

A lightweight, platform-agnostic Python client for sending Elite Dangerous journal data to the [CMDR Coriolis](https://cmdr.coriolis.io) service.

Designed for commanders who prefer a simple, open-source tool over existing third-party apps like EDMC, EDD or EDDI.

---

## Features

- **Cross-platform** – runs on Windows and Linux (macOS *should* work too).
- **Simple GUI** – built with Python's standard `tkinter` library; no extra UI dependencies.
- **Automatic journal detection** – finds the Elite Dangerous journal directory in the standard location, or you can point it at a custom path.
- **Live monitoring** – tails the latest journal file and sends tracked events to the Journal API as they appear. Automatically reads startup events (Commander, Materials, Loadout) from the current file and switches to new journal files when a new game session starts.
- **Smart filtering** – only sends events the API cares about (Commander, LoadGame, Loadout, ShipyardSwap, StoredShips, StoredModules, Materials, EngineerCraft). All other events are ignored locally.
- **CMDR name display** – read directly from your journal; cannot be spoofed.
- **Persistent settings** – API key and journal path are saved between sessions.

---

## Quick Start (no Python required)

Download the latest release for your platform from the [Releases page](https://github.com/Brighter-Applications/cmdr-coriolis-client/releases):

| Platform | Download |
|---|---|
| Windows | `CMDRCoriolisClient-windows.exe` |
| Linux | `CMDRCoriolisClient-linux` |

**Windows:** Double-click the `.exe` file. Windows SmartScreen may warn you the first time — click "More info" → "Run anyway". No installation needed.

**Linux:** Make the file executable and run it:
```bash
chmod +x CMDRCoriolisClient-linux
./CMDRCoriolisClient-linux
```

---

## Running from source (for developers)

If you prefer to run from source or want to modify the code:

### Requirements

- Python 3.10 or newer
- `tkinter` (included with most Python distributions; on some Linux distros install `python3-tk`)
- [requests](https://pypi.org/project/requests/) (see `requirements.txt`)

---

## Installation

```bash
# Clone the repository
git clone https://github.com/Brighter-Applications/cmdr-coriolis-client.git
cd cmdr-coriolis-client

# (Optional but recommended) create a virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux / macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## Running the app

```bash
python main.py
```

---

## Usage

1. **Enter your API key** – paste the key you received from [cmdr.coriolis.io](https://cmdr.coriolis.io) into the *API Key* field and press **Save Key**.
2. **Set the journal directory** – the app will try to auto-detect the standard location.
   If it isn't found, press **Browse…** and select the folder that contains your `Journal.*.log` files, then press **Apply**.
3. **Confirm your CMDR name** – once a journal file is found, your commander name is shown in the *Commander* section.  This is read directly from the journal and cannot be edited.
4. **Start monitoring** – press **Start Monitoring**.  The app will tail the latest journal file and send new events to the API in real time.  Status messages appear in the *Activity Log*.
5. **Stop monitoring** – press **Stop Monitoring** at any time.

---

## Default journal locations

| Platform | Path |
|---|---|
| Windows | `%USERPROFILE%\Saved Games\Frontier Developments\Elite Dangerous` |
| Linux (Steam/Proton) | `~/.local/share/Steam/steamapps/compatdata/359320/pfx/drive_c/users/steamuser/Saved Games/Frontier Developments/Elite Dangerous` |

---

## Configuration file

Settings are stored in:

| Platform | Path |
|---|---|
| Windows | `%APPDATA%\cmdr-coriolis-client\config.json` |
| Linux | `~/.config/cmdr-coriolis-client/config.json` |

You can edit this file by hand if needed.  It contains:

```json
{
  "api_key": "your-api-key-here",
  "journal_path": "/path/to/your/journal/directory"
}
```

---

## Project structure

```
cmdr-coriolis-client/
├── main.py            # Entry point
├── requirements.txt
├── client/
│   ├── __init__.py
│   ├── app.py         # tkinter GUI
│   ├── journal.py     # Journal file utilities
│   ├── api.py         # HTTP client for cmdr.coriolis.io
│   └── config.py      # Persistent settings
└── tests/
    ├── test_config.py
    ├── test_journal.py
    └── test_api.py
```

---

## Contributing / modifying

The code is intentionally kept simple so that you can read and modify it.  Each module is documented and contains no obfuscation.  Pull requests are welcome.

## Building the executable

To build the standalone executable yourself:

```bash
pip install pyinstaller
pyinstaller build.spec
```

The output will be in the `dist/` directory. On Windows this produces `CMDRCoriolisClient.exe`, on Linux it produces `CMDRCoriolisClient`.

---

## Licence

[MIT](LICENSE)
