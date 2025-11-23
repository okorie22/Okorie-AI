// Learn more about Tauri commands at https://tauri.app/develop/calling-rust/
use std::net::TcpStream;
use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::{Arc, Mutex};
use std::time::Duration;
use std::thread;
use std::fs::OpenOptions;
use std::io::Write;
use tauri::Manager;

// Store the server process so we can kill it when the app closes
static SERVER_PROCESS: once_cell::sync::Lazy<Arc<Mutex<Option<Child>>>> = 
    once_cell::sync::Lazy::new(|| Arc::new(Mutex::new(None)));

// Log to file for debugging (works even when console is closed)
fn log_to_file(message: &str) {
    #[cfg(windows)]
    {
        if let Ok(app_data) = std::env::var("APPDATA") {
            let log_path = PathBuf::from(&app_data)
                .join("Eliza Desktop")
                .join("eliza-desktop.log");
            
            // Create directory if it doesn't exist
            if let Some(parent) = log_path.parent() {
                let _ = std::fs::create_dir_all(parent);
            }
            
            if let Ok(mut file) = OpenOptions::new()
                .create(true)
                .append(true)
                .open(&log_path)
            {
                let timestamp = std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .map(|d| d.as_secs())
                    .unwrap_or(0);
                let _ = writeln!(file, "[{}] {}", timestamp, message);
            }
        }
    }
    
    // Always print to stderr too (visible in debug builds)
    eprintln!("{}", message);
}

macro_rules! log_error {
    ($($arg:tt)*) => {
        log_to_file(&format!($($arg)*));
    };
}

#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}

// Check if the server is running by attempting to connect to the port
fn is_server_running() -> bool {
    match TcpStream::connect("127.0.0.1:3000") {
        Ok(_) => true,
        Err(_) => false,
    }
}

// Wait for server to be ready with retry logic
fn wait_for_server(max_retries: u32) -> bool {
    for i in 0..max_retries {
        if is_server_running() {
            return true;
        }
        // Exponential backoff: 1s, 2s, 4s, 8s...
        let delay = Duration::from_secs(2_u64.pow(i.min(3)));
        thread::sleep(delay);
    }
    false
}

// Find the trading-brain project directory
fn find_project_directory() -> Option<PathBuf> {
    log_error!("Searching for trading-brain project...");

    // First, try environment variable (highest priority)
    if let Ok(env_path) = std::env::var("ELIZA_PROJECT_PATH") {
        log_error!("Checking ELIZA_PROJECT_PATH: {}", env_path);
        let path = PathBuf::from(env_path);
        if let Ok(canonical_path) = path.canonicalize() {
            if validate_project_directory(&canonical_path) {
                log_error!("Found trading-brain via ELIZA_PROJECT_PATH: {:?}", canonical_path);
                return Some(canonical_path);
            }
        }
    }

    // Try common development locations relative to user home
    if let Ok(home_dir) = std::env::var("USERPROFILE") {
        log_error!("Checking common dev locations from home: {}", home_dir);
        let home = PathBuf::from(home_dir);

        // Common locations where eliza projects might be
        let common_locations = vec![
            home.join("Civ").join("eliza").join("trading-brain"),
            home.join("Documents").join("Civ").join("eliza").join("trading-brain"),
            home.join("Desktop").join("Civ").join("eliza").join("trading-brain"),
            home.join("Projects").join("Civ").join("eliza").join("trading-brain"),
            home.join("eliza").join("trading-brain"),
            home.join("Civ").join("trading-brain"),
        ];

        for location in common_locations {
            if let Ok(canonical_path) = location.canonicalize() {
                if validate_project_directory(&canonical_path) {
                    log_error!("Found trading-brain in common location: {:?}", canonical_path);
                    return Some(canonical_path);
                }
            }
        }
    }

    // Try walking up from exe location (for installed apps)
    if let Ok(exe_path) = std::env::current_exe() {
        log_error!("Exe path: {:?}", exe_path);
        if let Some(mut current) = exe_path.parent() {
            // Walk up the directory tree looking for eliza/trading-brain
            for _ in 0..15 { // Go up 15 levels max
                log_error!("Checking directory: {:?}", current);

                // Check if current directory contains eliza/trading-brain
                let eliza_trading_brain = current.join("eliza").join("trading-brain");
                if let Ok(canonical_path) = eliza_trading_brain.canonicalize() {
                    if validate_project_directory(&canonical_path) {
                        log_error!("Found trading-brain walking up from exe: {:?}", canonical_path);
                        return Some(canonical_path);
                    }
                }

                // Check if current directory is eliza and contains trading-brain
                let trading_brain = current.join("trading-brain");
                if let Ok(canonical_path) = trading_brain.canonicalize() {
                    if validate_project_directory(&canonical_path) {
                        log_error!("Found trading-brain as sibling to exe: {:?}", canonical_path);
                        return Some(canonical_path);
                    }
                }

                // Go up one level
                if let Some(parent) = current.parent() {
                    current = parent;
                } else {
                    break;
                }
            }
        }
    }

    // Try relative to current working directory
    if let Ok(cwd) = std::env::current_dir() {
        log_error!("Current working directory: {:?}", cwd);

        // Try going up from CWD
        let mut current = cwd.as_path();
        for _ in 0..10 {
            let eliza_trading_brain = current.join("eliza").join("trading-brain");
            if let Ok(canonical_path) = eliza_trading_brain.canonicalize() {
                if validate_project_directory(&canonical_path) {
                    log_error!("Found trading-brain walking up from CWD: {:?}", canonical_path);
                    return Some(canonical_path);
                }
            }

            if let Some(parent) = current.parent() {
                current = parent;
            } else {
                break;
            }
        }
    }

    // Last resort: try some hardcoded common paths
    let fallback_paths = vec![
        PathBuf::from("C:\\Users\\Top Cash Pawn\\Civ\\eliza\\trading-brain"),
        PathBuf::from("C:\\Users\\Top Cash Pawn\\Documents\\Civ\\eliza\\trading-brain"),
        PathBuf::from("C:\\Users\\Top Cash Pawn\\Desktop\\Civ\\eliza\\trading-brain"),
    ];

    for path in fallback_paths {
        if let Ok(canonical_path) = path.canonicalize() {
            if validate_project_directory(&canonical_path) {
                log_error!("Found trading-brain in fallback location: {:?}", canonical_path);
                return Some(canonical_path);
            }
        }
    }

    log_error!("Could not find trading-brain project directory in any location");
    None
}

// Validate that a directory is the trading-brain project
fn validate_project_directory(path: &PathBuf) -> bool {
    if !path.exists() || !path.is_dir() {
        return false;
    }
    
    let package_json = path.join("package.json");
    if !package_json.exists() {
        return false;
    }
    
    if let Ok(contents) = std::fs::read_to_string(&package_json) {
        // Check for trading-brain in package.json name field
        contents.contains("\"name\": \"trading-brain\"") || 
        contents.contains("\"name\":\"trading-brain\"") ||
        contents.contains("trading-brain")
    } else {
        false
    }
}

// Find elizaos command, trying different options
fn find_elizaos_command() -> (String, Vec<String>) {
    #[cfg(windows)]
    {
        // On Windows, try bunx first, then elizaos
        match Command::new("bunx")
            .arg("--bun")
            .arg("elizaos")
            .arg("--version")
            .output()
        {
            Ok(_) => {
                log_error!("Found elizaos via bunx");
                return ("bunx".to_string(), vec!["--bun".to_string(), "elizaos".to_string()]);
            }
            Err(e) => {
                log_error!("bunx not found: {}", e);
                // Try elizaos directly
                match Command::new("elizaos").arg("--version").output() {
                    Ok(_) => {
                        log_error!("Found elizaos directly");
                        return ("elizaos".to_string(), vec![]);
                    }
                    Err(e2) => {
                        log_error!("Warning: Could not find elizaos command: {}. Make sure it's installed: bun i -g @elizaos/cli", e2);
                        return ("elizaos".to_string(), vec![]);
                    }
                }
            }
        }
    }
    
    #[cfg(not(windows))]
    {
        // On Unix-like systems, try elizaos directly
        match Command::new("elizaos").arg("--version").output() {
            Ok(_) => {
                log_error!("Found elizaos directly");
                ("elizaos".to_string(), vec![])
            }
            Err(e) => {
                log_error!("Warning: Could not find elizaos command: {}. Make sure it's installed: bun i -g @elizaos/cli", e);
                ("elizaos".to_string(), vec![])
            }
        }
    }
}

// Shutdown server when app exits
fn shutdown_server() {
    log_error!("Shutting down Eliza server...");
    match SERVER_PROCESS.lock() {
        Ok(mut guard) => {
            if let Some(ref mut child) = *guard {
                if let Err(e) = child.kill() {
                    log_error!("Failed to kill Eliza server: {}", e);
                } else {
                    log_error!("Eliza server shut down successfully");
                }
            }
            *guard = None;
        }
        Err(e) => {
            log_error!("Failed to lock SERVER_PROCESS mutex during shutdown: {}", e);
        }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    // Set up panic handler to log crashes
    std::panic::set_hook(Box::new(|panic_info| {
        let message = format!("PANIC: {:?}", panic_info);
        log_to_file(&message);
    }));
    
    log_error!("Starting Eliza Desktop App...");
    
    // Register cleanup for when app exits
    let app_result = tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![greet])
        .setup(|app| {
            log_error!("Tauri setup starting...");
            
            // Start the server if it's not already running
            if !is_server_running() {
                log_error!("Starting Eliza server...");
                
                // Find the project directory
                let project_dir = find_project_directory();
                
                if let Some(ref dir) = project_dir {
                    log_error!("Found trading-brain project at: {:?}", dir);
                } else {
                    log_error!("Warning: Could not find trading-brain project directory");
                    log_error!("Current exe: {:?}", std::env::current_exe());
                    log_error!("Current dir: {:?}", std::env::current_dir());
                    log_error!("Trying to start from current directory...");
                }
                
                // Determine if we're in dev mode
                let is_dev = std::env::var("TAURI_DEV").is_ok() || cfg!(debug_assertions);
                let command = if is_dev { "dev" } else { "start" };
                log_error!("Running in {} mode, using 'elizaos {}'", 
                    if is_dev { "development" } else { "production" }, 
                    command);
                
                // Find elizaos command
                let (cmd_name, mut cmd_args) = find_elizaos_command();
                cmd_args.push("--no-emoji".to_string()); // Disable emoji to avoid issues
                cmd_args.push(command.to_string());

                // Build the command
                let mut cmd = Command::new(&cmd_name);
                for arg in &cmd_args {
                    cmd.arg(arg);
                }
                
                // Set working directory if we found the project
                if let Some(ref dir) = project_dir {
                    cmd.current_dir(dir);
                    log_error!("Setting working directory to: {:?}", dir);
                }
                
                // Set environment variables for the child process
                cmd.env("ELIZA_USE_LOCAL_SERVER", "true");
                // Disable update check to prevent npm dependency errors
                cmd.env("CI", "true");
                cmd.env("NO_UPDATE_CHECK", "1");
                cmd.env("ELIZA_TEST_MODE", "true"); // Also skip update checks
                cmd.env("ELIZA_CLI_TEST_MODE", "true");
                cmd.env("ELIZA_SKIP_LOCAL_CLI_DELEGATION", "true");
                // Prevent npm from being called
                cmd.env("npm_config_update_notifier", "false");
                // Disable any banner/display that might call npm
                cmd.env("NO_COLOR", "true");
                
                // Start the server
                match cmd.spawn() {
                    Ok(child) => {
                        // Store the process so we can kill it when the app closes
                        match SERVER_PROCESS.lock() {
                            Ok(mut server_guard) => {
                                *server_guard = Some(child);
                                log_error!("Eliza server process started");
                                
                                // Wait for server to be ready (in background)
                                thread::spawn(move || {
                                    if wait_for_server(10) {
                                        log_error!("Eliza server is ready");
                                    } else {
                                        log_error!("Warning: Eliza server may not be ready yet");
                                    }
                                });
                            }
                            Err(e) => {
                                log_error!("Failed to lock SERVER_PROCESS mutex: {}", e);
                            }
                        }
                    },
                    Err(e) => {
                        log_error!("Failed to start Eliza server: {}", e);
                        log_error!("Make sure 'elizaos' is installed globally: bun i -g @elizaos/cli");
                        if let Some(ref dir) = project_dir {
                            log_error!("Project directory: {:?}", dir);
                        }
                        // Don't crash - just log the error and continue
                    }
                };
            } else {
                log_error!("Eliza server is already running");
            }
            
            // Add event listener for app exit
            let _app_handle = app.handle();
            
            #[cfg(desktop)]
            {
                if let Some(main_window) = app.get_webview_window("main") {
                    main_window.on_window_event(move |event| {
                        if let tauri::WindowEvent::CloseRequested { .. } = event {
                            shutdown_server();
                        }
                    });
                }
            }
            
            log_error!("Tauri setup complete");
            Ok(())
        })
        .build(tauri::generate_context!());
    
    match app_result {
        Ok(app) => {
            log_error!("Tauri app built successfully, starting...");
            app.run(|_app_handle, event| {
                if let tauri::RunEvent::Exit = event {
                    shutdown_server();
                }
            });
        }
        Err(e) => {
            log_error!("Failed to build Tauri application: {}", e);
            // Try to show error message box on Windows
            #[cfg(windows)]
            {
                use std::ffi::CString;
                use winapi::um::winuser::{MessageBoxA, MB_OK, MB_ICONERROR};
                let title = CString::new("Eliza Desktop Error").unwrap_or_default();
                let msg_str = format!("Failed to start Eliza Desktop App:\n\n{}\n\nCheck the log file at:\n%APPDATA%\\Eliza Desktop\\eliza-desktop.log", e);
                if let Ok(msg) = CString::new(msg_str) {
                    unsafe {
                        MessageBoxA(std::ptr::null_mut(), msg.as_ptr(), title.as_ptr(), MB_OK | MB_ICONERROR);
                    }
                }
            }
        }
    }
}
