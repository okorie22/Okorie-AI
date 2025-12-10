# Desktop App Setup & Installation

## Quick Start

The desktop app has been built and is ready to install!

### Install the Desktop App

**Option 1: MSI Installer (Recommended)**
```
C:\Users\Top Cash Pawn\Civ\eliza\packages\app\src-tauri\target\release\bundle\msi\Eliza Desktop_1.6.4_x64_en-US.msi
```

**Option 2: NSIS Installer**
```
C:\Users\Top Cash Pawn\Civ\eliza\packages\app\src-tauri\target\release\bundle\nsis\Eliza Desktop_1.6.4_x64-setup.exe
```

Double-click either installer to install the desktop app.

## What the Desktop App Does

1. **Automatically finds** the `trading-brain` project directory
2. **Starts the ElizaOS server** (`elizaos dev`) when you launch the app
3. **Loads the web interface** from `http://localhost:3000` in an embedded window
4. **Reflects code changes automatically** - no rebuild needed when you modify trading-brain code
5. **Shuts down cleanly** when you close the app

## First Launch

When you first launch the desktop app:

1. It will search for the `trading-brain` project in these locations (in order):
   - `ELIZA_PROJECT_PATH` environment variable (if set)
   - Relative to app installation: `../../trading-brain`, `../trading-brain`, etc.
   - Current working directory

2. If it finds the project, it will:
   - Start `elizaos dev` from that directory
   - Wait for the server to be ready (shows loading screen)
   - Display the ElizaOS interface once ready

3. If it can't find the project:
   - You'll see an error message
   - Set the `ELIZA_PROJECT_PATH` environment variable to point to your trading-brain directory

## Setting Custom Project Path (If Needed)

If the app can't find your trading-brain project automatically:

**Windows PowerShell:**
```powershell
$env:ELIZA_PROJECT_PATH="C:\Users\Top Cash Pawn\Civ\eliza\trading-brain"
```

**Windows CMD:**
```cmd
set ELIZA_PROJECT_PATH=C:\Users\Top Cash Pawn\Civ\eliza\trading-brain
```

To make it permanent, add it to System Environment Variables.

## Requirements

- **ElizaOS CLI** must be installed: `bun i -g @elizaos/cli`
- **Trading-brain project** must be accessible (see paths above)
- **Port 3000** must be available (or the server won't start)

## Troubleshooting

### "Failed to start Eliza server"
- Make sure `elizaos` is installed: `bun i -g @elizaos/cli`
- Check that the trading-brain directory is accessible
- Verify port 3000 is not in use

### "Cannot find trading-brain project"
- Set `ELIZA_PROJECT_PATH` environment variable
- Ensure the project has a `package.json` with `"name": "trading-brain"`

### Server takes too long to start
- Check that Ollama is running (if using local models)
- Verify `.env` file is properly configured
- Check console/terminal for error messages

## Rebuilding the Desktop App

If you need to rebuild (only needed when Rust/Tauri code changes):

```bash
cd eliza/packages/app
bun run tauri:build:installer
```

The new installers will be in `src-tauri/target/release/bundle/`.

## Notes

- **Code changes in trading-brain are automatically reflected** - the desktop app loads from localhost:3000, so you don't need to rebuild the desktop app when you modify trading-brain code
- **Only rebuild the desktop app** when you change Rust code in `src-tauri/src/lib.rs` or Tauri configuration
- The desktop app runs the server in **development mode** (`elizaos dev`) for hot-reload support

