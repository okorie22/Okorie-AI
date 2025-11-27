// ITORO Server Startup - Clean and Simple
console.log('🚀 Starting ITORO Server...');

let AgentServer, project, resolve, readFileSync;

try {
  console.log('Loading dependencies...');

  // Synchronous imports first
  const fs = await import('fs');
  const path = await import('path');
  readFileSync = fs.readFileSync;
  resolve = path.resolve;

  console.log('✓ Core modules loaded');

  console.log('Loading AgentServer...');
  const serverModule = await import('@elizaos/server');
  AgentServer = serverModule.AgentServer;
  console.log('✓ AgentServer loaded');

  console.log('Loading project config...');
  const projectModule = await import('./index.ts');
  project = projectModule.default;
  console.log('✓ Project config loaded');

} catch (error) {
  console.error('✗ CRITICAL: Failed to load core modules');
  console.error('Error:', error.message);
  console.error('Stack:', error.stack);
  process.exit(1);
}

function loadEnv() {
  try {
    const envPath = resolve('../.env');
    console.log(`Loading .env from: ${envPath}`);

    const envContent = readFileSync(envPath, 'utf8');
    const lines = envContent.split('\n').filter(line =>
      line.trim() && !line.startsWith('#')
    );

    for (const line of lines) {
      const equalIndex = line.indexOf('=');
      if (equalIndex > 0) {
        const key = line.substring(0, equalIndex).trim();
        const value = line.substring(equalIndex + 1).trim();
        process.env[key] = value;
        console.log(`✓ Set ${key}`);
      }
    }

    console.log('✓ Environment variables loaded');
  } catch (error) {
    console.error('✗ Failed to load .env:', error.message);
  }
}

// Import plugins directly
async function loadPlugins() {
  console.log('Loading plugins...');

  const plugins = [];

  try {
    const bootstrapModule = await import('@elizaos/plugin-bootstrap');
    const bootstrap = bootstrapModule.default || bootstrapModule.bootstrapPlugin;
    if (bootstrap) {
      plugins.push(bootstrap);
      console.log(`✓ Bootstrap plugin: ${bootstrap.name}`);
    }
  } catch (error) {
    console.error('✗ Failed to load bootstrap plugin:', error.message);
  }

  try {
    console.log('⚠ Temporarily skipping ITORO bridge plugin due to SQLite issues');
    console.log('⚠ Bridge plugin will be loaded after SQLite is fixed');
    // const itoroModule = await import('@elizaos/plugin-itoro-bridge');
    // const itoro = itoroModule.default || itoroModule.itoroBridgePlugin;
    // if (itoro) {
    //   plugins.push(itoro);
    //   console.log(`✓ ITORO bridge plugin: ${itoro.name}`);
    // }
  } catch (error) {
    console.error('✗ Failed to load ITORO bridge plugin:', error.message);
  }

  return plugins;
}

// Main startup
async function start() {
  console.log('🚀 Starting ITORO Server...');

  // Load environment first
  loadEnv();

  // Load plugins
  const plugins = await loadPlugins();

  if (plugins.length === 0) {
    console.error('✗ No plugins loaded - cannot start server');
    process.exit(1);
  }

  try {
    // Create and initialize server
    const server = new AgentServer();
    console.log('Initializing server...');
    await server.initialize();

    // Start agents
    if (project.agents && project.agents.length > 0) {
      const characters = project.agents.map(agent => agent.character);
      console.log(`Starting ${characters.length} agent(s) with ${plugins.length} plugins...`);
      await server.startAgents(characters, plugins);
    } else {
      console.error('✗ No agents defined in project');
      process.exit(1);
    }

    // Start HTTP server
    await server.start(3000);
    console.log('✅ ITORO Server running on http://localhost:3000');
    console.log('✅ ITORO can now chat and access trading agents!');

  } catch (error) {
    console.error('✗ Server startup failed:', error.message);
    console.error(error.stack);
    process.exit(1);
  }
}

// Handle uncaught errors
process.on('uncaughtException', (error) => {
  console.error('Uncaught exception:', error);
  process.exit(1);
});

process.on('unhandledRejection', (reason) => {
  console.error('Unhandled rejection:', reason);
  process.exit(1);
});

// Start the server
start();
