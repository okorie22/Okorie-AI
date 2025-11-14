-- Migration: Add ngrok_url column to local_ip_registrations table
-- Purpose: Store ngrok URL alongside IP registration for automatic webhook forwarding
-- Created: 2025-01-22

-- Add ngrok_url column to existing table
ALTER TABLE local_ip_registrations 
ADD COLUMN IF NOT EXISTS ngrok_url VARCHAR(255);

-- Add comment to the new column
COMMENT ON COLUMN local_ip_registrations.ngrok_url IS 'ngrok public URL for webhook forwarding (e.g., https://abc123.ngrok-free.dev)';

-- Create index for efficient querying by ngrok_url
CREATE INDEX IF NOT EXISTS idx_local_ip_registrations_ngrok_url 
ON local_ip_registrations(ngrok_url) 
WHERE ngrok_url IS NOT NULL;
