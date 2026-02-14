<h1 align="center">Collector Games</h1>
An automatic game collector with a 100% discount on Steam, featuring easy background monitoring via the requests library and integration into the system tray for simple and convenient configuration when needed..

## Workflow
1. **Monitoring**: Lightweight request via Requests to check for new games.
2. **Comparison**: Comparing data with the local database.
3. **Automation**: If new games are detected, Playwright is launched to perform subsequent actions (JS processing).
4. **Cooldown**: The program enters a 5-hour waiting mode, after which the cycle repeats.

## Tech Stack
- **python 3.13**
- **Requests + BeautifulSoup4 (lxml)** — fast update monitoring and static content parsing.
- **Playwright** — browser automation for interacting with elements (adding games) that execute JS.
- **APScheduler** — task scheduling and interval management.
- **Loguru** — extended event logging.
- **JSON** — local data storage.
- **psutil** — system process management and forced browser termination.

## Installation

!Important: Python 3.13+ must be installed on your system. When installing Python, make sure to check the "Add Python to PATH" box.

### Option 1: For users without Git
1. Download the [ZIP archive](https://github.com/Falltiker/collector-games/archive/refs/heads/main.zip) and extract it.
2. Run the [setup.bat](setup.bat) script, which will create the environment and install dependencies.

### Option 2: Via Git
```Bash
git clone https://github.com/Falltiker/collector-games.git
cd collector-games
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```
## Usage
1. Run the run.bat script once for manual Steam authorization.
2. Run enable_autostart.bat to enable program autostart on PC boot.

## Project Architecture
```Bash
collector-games
├─ config
│  └─ chrome_config.json    # Browser configuration
├─ data
│  └─ games.json            # Data storage (games database)
├─ src
│  ├─ automation.py         # Playwright
│  ├─ collector.py          # Requests
│  └─ utils
│     └─ chrome_manager.py  # Browser instance manager
├─ main.py                  # Entry point
├─ run.bat                  # Fast start script
├─ enable_autostart.bat     # Script for setting up autostart
├─ setup.bat                # Automatic environment setup script
└─ start.vbs                # Script for silent program operation
```

- [Chrome Manager](src/utils/chrome_manager.py): custom module for browser initialization in a few lines of code. Easy configuration of context and launch parameters.
- Automation: The project includes .vbs and .bat scripts for configuring Windows autostart, allowing the parser to run in the background without user intervention.
- Dependencies: Full list of libraries available in [requirements.txt](requirements.txt).