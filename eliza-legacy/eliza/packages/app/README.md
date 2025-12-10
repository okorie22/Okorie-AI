# Eliza Desktop App

A Tauri-based desktop application wrapper for ElizaOS that automatically starts the server and loads the web interface.

## Overview

The Eliza Desktop App is a lightweight wrapper that:
- Automatically finds and starts the ElizaOS server from the `trading-brain` project
- Loads the web interface from `http://localhost:3000` in an embedded iframe
- Automatically reflects code changes without requiring rebuilds (since it loads from localhost)
- Provides a native desktop experience on Windows, macOS, and Linux

## Architecture

The desktop app consists of:
- **Rust Backend** (`src-tauri/src/lib.rs`): Handles server startup, process management, and cleanup
- **React Frontend** (`src/main.tsx`): Provides the UI wrapper and server health checking
- **Tauri Framework**: Bridges Rust and web technologies for native desktop apps

### How Automatic Updates Work

The desktop app loads the ElizaOS interface from `http://localhost:3000`, which means:
- Code changes in `trading-brain` are immediately visible (no rebuild needed)
- The desktop app only needs rebuilding when Rust/Tauri code changes
- The server runs in development mode (`elizaos dev`) for hot-reload support

## Prerequisites

- [Bun](https://bun.sh/) installed globally
- [Rust](https://www.rust-lang.org/tools/install) and [Tauri prerequisites](https://tauri.app/v1/guides/getting-started/prerequisites)
- ElizaOS CLI installed: `bun i -g @elizaos/cli`
- The `trading-brain` project must be accessible (see Project Directory Detection below)

## Development

### Running in Development Mode

```bash
cd eliza/packages/app
bun install
bun run start
# or
bun run tauri:dev
```

This will:
1. Start the Tauri dev server
2. Automatically find and start `elizaos dev` from the trading-brain project
3. Load the web interface in the desktop app

### Building the Desktop App

#### Development Build
```bash
bun run tauri:build
```

#### Windows-Specific Build
```bash
bun run tauri:build:windows
```

#### Build with Installers (MSI/NSIS)
```bash
bun run tauri:build:installer
```

The built application will be in `src-tauri/target/release/` (or `target/debug/` for debug builds).

## Installation

### Windows

After building, you'll find installers in `src-tauri/target/release/bundle/`:
- **MSI Installer**: `msi/Eliza Desktop_1.6.4_x64_en-US.msi`
- **NSIS Installer**: `nsis/Eliza Desktop_1.6.4_x64-setup.exe`

Run either installer to install the desktop app.

### macOS

The `.app` bundle will be in `src-tauri/target/release/bundle/macos/`.

### Linux

The AppImage or other package formats will be in `src-tauri/target/release/bundle/`.

## Project Directory Detection

The desktop app automatically searches for the `trading-brain` project in the following order (highest priority first):

1. **Environment variable**: `ELIZA_PROJECT_PATH` (if set, this takes priority)
2. **Relative to executable**: `../../trading-brain`, `../trading-brain`, `./trading-brain`, `../../../trading-brain`
3. **Relative to current working directory**: Same relative paths as above

The app validates the directory by checking for a `package.json` file containing `"name": "trading-brain"`. This ensures it finds the correct project even if there are similarly named directories.

### Setting Custom Project Path

You can set the `ELIZA_PROJECT_PATH` environment variable to point to your trading-brain project:

**Windows (PowerShell):**
```powershell
$env:ELIZA_PROJECT_PATH="C:\path\to\trading-brain"
```

**Windows (CMD):**
```cmd
set ELIZA_PROJECT_PATH=C:\path\to\trading-brain
```

**macOS/Linux:**
```bash
export ELIZA_PROJECT_PATH=/path/to/trading-brain
```

## Server Management

### Automatic Server Startup

The desktop app automatically:
- Checks if a server is already running on port 3000
- Starts `elizaos dev` (in dev mode) or `elizaos start` (in production)
- Waits for the server to be ready before showing the interface
- Shuts down the server when the app closes

### Manual Server Control

If you prefer to start the server manually:
1. Start the server yourself: `cd trading-brain && elizaos dev`
2. The desktop app will detect it's already running and use it

## Troubleshooting

### Server Fails to Start

**Error**: "Failed to start Eliza server"

**Solutions**:
1. Ensure `elizaos` is installed globally: `bun i -g @elizaos/cli`
2. On Windows, the app tries `bunx --bun elizaos` if `elizaos` isn't found
3. Check that the trading-brain project directory is accessible
4. Verify port 3000 is not in use by another application
5. Check that all required environment variables are set in `.env`

### Cannot Find Trading-Brain Project

**Error**: "Warning: Could not find trading-brain project directory"

**Solutions**:
1. Set the `ELIZA_PROJECT_PATH` environment variable
2. Ensure the project is in a relative location (see Project Directory Detection)
3. Verify `package.json` exists and contains `"name": "trading-brain"`

### Server Takes Too Long to Start

**Symptom**: Loading screen appears for more than 30 seconds

**Solutions**:
1. Check server logs in the console/terminal
2. Verify Ollama is running (if using local models)
3. Check that all dependencies are installed in trading-brain
4. Ensure `.env` file is properly configured

### Interface Doesn't Load

**Symptom**: Error message appears after server starts

**Solutions**:
1. Open `http://localhost:3000` in a browser to verify the server is working
2. Check browser console for CORS or CSP errors
3. Verify the server is responding to `/api/server/ping`
4. Check Tauri CSP settings in `tauri.conf.json`

### Port 3000 Already in Use

**Error**: Server can't bind to port 3000

**Solutions**:
1. Close other applications using port 3000
2. Change the server port in trading-brain configuration
3. Update the desktop app to use the new port (requires code changes)

## Development Tips

### Hot Reload

- Changes to React/TypeScript code: Automatically reloaded by Vite
- Changes to Rust code: Requires restart (`Ctrl+C` and `bun run start`)
- Changes to trading-brain code: Automatically reflected (server runs in dev mode)

### Debugging

- **Rust Backend**: Use `println!` or `eprintln!` for logging (visible in terminal)
- **React Frontend**: Use browser DevTools (right-click in app → Inspect)
- **Server Logs**: Check the terminal where `elizaos dev` is running

### Building for Distribution

1. Update version in `package.json` and `tauri.conf.json`
2. Build: `bun run tauri:build:installer`
3. Test the installer on a clean system
4. Distribute the installer from `src-tauri/target/release/bundle/`

## Configuration

### Tauri Configuration

Edit `src-tauri/tauri.conf.json` to:
- Change app name, version, or identifier
- Modify window size or behavior
- Update CSP (Content Security Policy) settings
- Configure bundle settings

### Server Configuration

The server uses configuration from the `trading-brain` project:
- Environment variables from `.env`
- Character settings from `src/character.ts`
- Plugin configurations

## Version Compatibility

- **ElizaOS**: 1.6.4
- **Tauri**: 2.0.0
- **React**: 19.1.0
- **Rust**: Edition 2021

## Support

For issues related to:
- **Desktop App**: Check this README and Tauri documentation
- **ElizaOS Server**: Check trading-brain project documentation
- **General ElizaOS**: Visit [ElizaOS Documentation](https://docs.eliza.how)
