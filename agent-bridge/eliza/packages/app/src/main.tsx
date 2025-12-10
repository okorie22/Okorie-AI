import React from 'react';
import ReactDOM from 'react-dom/client';
// Using a simple try/catch for the Eliza server, avoiding Tauri API dependencies
import { useEffect, useState } from 'react';

// Component that will redirect the user to the Eliza client
function ElizaWrapper() {
  const [status, setStatus] = useState<'starting' | 'running' | 'error'>('starting');
  const [error, setError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);
  const [isServerAccessible, setIsServerAccessible] = useState(false);

  // Function to check if server is accessible
  const checkServerAccessibility = async () => {
    console.log('Checking server accessibility...');

    // First try - health endpoint with CORS
    try {
      console.log('Trying /health endpoint...');
      const response = await fetch('http://localhost:3000/health', {
        method: 'GET',
        mode: 'cors',
        cache: 'no-cache',
      });
      console.log('Health endpoint response:', response.status);
      if (response.ok) {
        console.log('Health check passed!');
        return true;
      }
    } catch (e) {
      console.log('Health endpoint failed:', e);
    }

    // Second try - simple fetch without CORS
    try {
      console.log('Trying simple fetch...');
      const response = await fetch('http://localhost:3000', {
        method: 'HEAD',
        mode: 'no-cors',
      });
      console.log('Simple fetch succeeded');
      return true;
    } catch (e) {
      console.log('Simple fetch failed:', e);
    }

    // Third try - check if port is responding (this should work)
    try {
      console.log('Checking WebSocket connection...');
      // Try to connect to WebSocket (server has Socket.IO)
      const ws = new WebSocket('ws://localhost:3000');
      return new Promise((resolve) => {
        ws.onopen = () => {
          console.log('WebSocket connected - server is running!');
          ws.close();
          resolve(true);
        };
        ws.onerror = () => {
          console.log('WebSocket failed');
          resolve(false);
        };
        // Timeout after 2 seconds
        setTimeout(() => {
          ws.close();
          resolve(false);
        }, 2000);
      });
    } catch (e) {
      console.log('WebSocket check failed:', e);
      return false;
    }
  };

  // Start the Eliza server
  useEffect(() => {
    const startServer = async () => {
      try {
        setStatus('running');

        // Start polling to check if the server is accessible
        let attemptCount = 0;
        const maxAttempts = 15; // Reduced to 15 attempts
        console.log('Starting server health checks...');

        const checkServer = async () => {
          attemptCount++;
          console.log(`Health check attempt ${attemptCount}/${maxAttempts}`);
          const isAccessible = await checkServerAccessibility();

          if (isAccessible) {
            console.log('Server is accessible! Showing interface...');
            setIsServerAccessible(true);
            setStatus('running');
          } else if (attemptCount >= maxAttempts) {
            console.log('Max attempts reached, showing interface anyway...');
            // Even if health check fails, show the interface
            // The server might be running but health check is blocked by CORS
            setIsServerAccessible(true);
            setStatus('running');
          } else {
            // Faster checks: 1s, 1.5s, 2s, then 1s intervals
            const delay = attemptCount <= 2 ? 1000 : 1000;
            console.log(`Retrying in ${delay}ms...`);
            setTimeout(checkServer, delay);
          }
        };

        // Start checking immediately
        checkServer();
      } catch (err: unknown) {
        console.error('Failed to start Eliza server:', err);
        setStatus('error');
        setError(
          `Failed to start Eliza server: ${err instanceof Error ? err.message : String(err)}`
        );
      }
    };

    startServer();
  }, [retryCount]); // Dependency on retryCount allows us to retry

  // Retry handler
  const handleRetry = () => {
    setStatus('starting');
    setError(null);
    setRetryCount((prev) => prev + 1);
  };

  // If the server is running and accessible, show the iframe
  if (status === 'running' && isServerAccessible) {
    return (
      <div style={{ width: '100%', height: '100vh', margin: 0, padding: 0 }}>
        <iframe
          src="http://localhost:3000"
          title="Eliza Client"
          style={{
            width: '100%',
            height: '100%',
            border: 'none',
          }}
        />
      </div>
    );
  }

  // Show loading or error message
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        padding: '20px',
        textAlign: 'center',
        fontFamily: 'sans-serif',
      }}
    >
      {status === 'error' ? (
        <>
          <h2 style={{ color: '#d32f2f', marginBottom: '16px' }}>Server Error</h2>
          <p style={{ marginBottom: '8px', color: '#666' }}>{error}</p>
          <p style={{ marginBottom: '20px', fontSize: '14px', color: '#888' }}>
            Make sure the ElizaOS server can start properly. Check that:
          </p>
          <ul style={{ textAlign: 'left', marginBottom: '20px', color: '#666', fontSize: '14px' }}>
            <li>Ollama is running (if using local models)</li>
            <li>All required environment variables are set in .env</li>
            <li>The trading-brain project directory is accessible</li>
            <li>Port 3000 is not already in use by another application</li>
          </ul>
          <button
            type="button"
            onClick={handleRetry}
            style={{
              marginTop: '20px',
              padding: '12px 24px',
              backgroundColor: '#0078d7',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '16px',
              fontWeight: '500',
            }}
            onMouseOver={(e) => {
              e.currentTarget.style.backgroundColor = '#0066bb';
            }}
            onMouseOut={(e) => {
              e.currentTarget.style.backgroundColor = '#0078d7';
            }}
          >
            Retry
          </button>
        </>
      ) : (
        <>
          <h2>Starting Eliza Server...</h2>
          <p>Please wait while we start the backend services.</p>
          <div
            style={{
              marginTop: '20px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <div
              style={{
                width: '20px',
                height: '20px',
                borderRadius: '50%',
                border: '2px solid #ccc',
                borderTopColor: '#0078d7',
                animation: 'spin 1s linear infinite',
              }}
            />
            <style>
              {`
                @keyframes spin {
                  to { transform: rotate(360deg); }
                }
              `}
            </style>
          </div>
        </>
      )}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <ElizaWrapper />
  </React.StrictMode>
);
