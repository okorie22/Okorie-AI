-- Migration: Create local_ip_registrations table
-- Purpose: Store local machine IP registrations for webhook forwarding
-- Created: 2025-01-14

CREATE TABLE IF NOT EXISTS local_ip_registrations (
    id SERIAL PRIMARY KEY,
    public_ip VARCHAR(45) NOT NULL,
    local_ip VARCHAR(45),
    port INTEGER NOT NULL DEFAULT 8080,
    hostname VARCHAR(255),
    registered_at TIMESTAMP DEFAULT NOW(),
    last_seen TIMESTAMP DEFAULT NOW()
);

-- Create unique constraint on public_ip and port combination
-- This allows updates when the same IP/port combination registers again
CREATE UNIQUE INDEX IF NOT EXISTS idx_local_ip_registrations_unique 
ON local_ip_registrations(public_ip, port);

-- Create index for efficient querying by timestamp
CREATE INDEX IF NOT EXISTS idx_local_ip_registrations_timestamp 
ON local_ip_registrations(registered_at DESC);

-- Create index for efficient querying by last_seen
CREATE INDEX IF NOT EXISTS idx_local_ip_registrations_last_seen 
ON local_ip_registrations(last_seen DESC);

-- Add comment to table
COMMENT ON TABLE local_ip_registrations IS 'Stores local machine IP registrations for automatic webhook forwarding from Render to local development machines';
COMMENT ON COLUMN local_ip_registrations.public_ip IS 'Public IP address of the local machine';
COMMENT ON COLUMN local_ip_registrations.local_ip IS 'Local network IP address of the machine';
COMMENT ON COLUMN local_ip_registrations.port IS 'Port number where the local webhook server is running';
COMMENT ON COLUMN local_ip_registrations.hostname IS 'Hostname of the local machine';
COMMENT ON COLUMN local_ip_registrations.registered_at IS 'When this IP was first registered';
COMMENT ON COLUMN local_ip_registrations.last_seen IS 'When this IP was last seen (updated on each registration)';
