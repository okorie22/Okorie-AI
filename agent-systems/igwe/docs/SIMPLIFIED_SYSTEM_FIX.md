# Complete System Simplification & Fix

## What Was Fixed

### 1. Case-Insensitive Email Matching
**Problem**: `okemokorie@yahoo.com` didn't match `OkemOkorie@yahoo.com` in the database.

**Fix**: Updated `LeadRepository.get_by_email()` to use SQL `LOWER()` function for case-insensitive matching.

**File**: `src/storage/repositories.py`

### 2. Reply Agent Configuration Bug
**Problem**: Reply agent was using wrong config path (`app_config.llm_config` instead of `llm_config`).

**Fix**: Changed to use correct `llm_config` import.

**File**: `src/api/main.py` (line 266)

### 3. Notifications for ALL Inbounds
**Problem**: Only known leads triggered notifications. Unknown senders were ignored.

**Fix**: Added notification call in the "unknown sender" branch so ALL inbounds send notifications.

**File**: `src/api/main.py` (inbound handler)

### 4. Compose by Raw Email
**Problem**: Compose dropdown required selecting from recent conversations. You couldn't type a raw email.

**Fix**: 
- Changed compose form to accept raw email input
- Updated backend to find/create lead from email if not in dropdown
- Removed requirement to select from suggestions

**Files**: 
- `src/api/messages_dashboard.py` (form HTML)
- `src/api/messages_dashboard.py` (JavaScript validation)
- `src/api/messages_dashboard.py` (`/messages/send` endpoint)

### 5. Simple Lead Import Script
**Problem**: No easy way to manually add leads.

**Fix**: Created `scripts/import_lead.py` - just run it and answer prompts.

**File**: `scripts/import_lead.py` (NEW)

## How to Use

### Import a Lead

```bash
# On your VM or local:
cd agent-systems/igwe
export DATABASE_URL="your_postgres_url"
python scripts/import_lead.py
```

It will prompt you for:
- Email (required)
- First name (optional)
- Last name (optional)
- Phone (optional)
- Company (optional)

The script will:
1. Check if lead exists (case-insensitive)
2. Create lead if new
3. Create conversation for the lead
4. Print confirmation

### Compose to Anyone

1. Go to `/messages` dashboard
2. Click "Compose"
3. Type ANY email address in the "To" field
4. Fill in subject and message
5. Send

The system will:
- Find existing lead by email (case-insensitive)
- OR create a new lead automatically
- Create a conversation if needed
- Send the email

### Test Notifications

Send any email to `info@mail.reimaginewealth.org` from ANY address.

You should:
1. See it in the dashboard (`/messages`)
2. Receive notification at `contact@okemokorie.com`
3. If sender is a known lead, AI will analyze and respond

## Deploy to VM

```bash
# On your VM
cd ~/Okorie-AI
git pull origin main
screen -r igwe  # or your screen session name
# Ctrl+C to stop the app
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
# Ctrl+A, D to detach
```

## Summary

The system is now much simpler:

1. **Email matching works** (case-insensitive)
2. **Reply agent uses correct config** (will actually run)
3. **All inbounds trigger notifications** (known or unknown)
4. **Compose accepts raw emails** (no dropdown required)
5. **Easy lead import** (just run the script)

No more complexity. Just send and receive emails.
