# Webhook Address Sync System

This system automatically keeps your Helius webhook addresses in sync with your `WALLETS_TO_TRACK` configuration.

## Overview

The webhook address sync system ensures that:
1. **Your personal wallet is always included** (never removed)
2. **New wallets from `WALLETS_TO_TRACK` are automatically added**
3. **Old wallets not in `WALLETS_TO_TRACK` are automatically removed**
4. **Your Helius webhook is updated with the correct address list**

## How It Works

### Automatic Sync (Recommended)
The webhook server automatically syncs addresses when it starts up. This happens in the background and ensures your webhook is always up-to-date.

### Manual Sync
You can also manually sync addresses using the standalone script:

```bash
python src/scripts/sync_webhook_addresses.py
```

## Configuration

### 1. Set Environment Variables

Make sure you have these environment variables set:

```bash
export HELIUS_API_KEY=your_helius_api_key_here
export DEFAULT_WALLET_ADDRESS=your_personal_wallet_address_here
```

### 2. Update WALLETS_TO_TRACK

Edit your `src/config.py` file and update the `WALLETS_TO_TRACK` list:

```python
WALLETS_TO_TRACK = [
    "DYAn4XpAkN5mhiXkRB7dGq4Jadnx6XYgu8L5b3WGhbrt",  # KayTheDoc (Score: 0.364)
    "86AEJExyjeNNgcp7GrAvCXTDicf5aGWgoERbXFiG1EdD",  # publixplays (Score: 0.355)
    "4DdrfiDHpmx55i4SPssxVzS9ZaKLb8qr45NKY9Er9nNh",  # TheMisterFrog (Score: 0.353)
    # Add new wallets here...
]
```

## Usage Examples

### Example 1: Adding a New Wallet

1. Add the new wallet to `WALLETS_TO_TRACK` in `src/config.py`:
```python
WALLETS_TO_TRACK = [
    "DYAn4XpAkN5mhiXkRB7dGq4Jadnx6XYgu8L5b3WGhbrt",
    "86AEJExyjeNNgcp7GrAvCXTDicf5aGWgoERbXFiG1EdD",
    "4DdrfiDHpmx55i4SPssxVzS9ZaKLb8qr45NKY9Er9nNh",
    "NEW_WALLET_ADDRESS_HERE",  # New wallet
]
```

2. Run the sync script:
```bash
python src/scripts/sync_webhook_addresses.py
```

3. The script will show:
```
📋 Changes Required:
➕ Addresses to add (1):
    NEW_WALLET...
🔄 Proceeding with webhook update...
✅ Webhook successfully updated
```

### Example 2: Removing a Wallet

1. Remove the wallet from `WALLETS_TO_TRACK` in `src/config.py`:
```python
WALLETS_TO_TRACK = [
    "DYAn4XpAkN5mhiXkRB7dGq4Jadnx6XYgu8L5b3WGhbrt",
    "86AEJExyjeNNgcp7GrAvCXTDicf5aGWgoERbXFiG1EdD",
    # Removed: "4DdrfiDHpmx55i4SPssxVzS9ZaKLb8qr45NKY9Er9nNh"
]
```

2. Run the sync script:
```bash
python src/scripts/sync_webhook_addresses.py
```

3. The script will show:
```
📋 Changes Required:
➖ Addresses to remove (1):
    TheMisterF...
🔄 Proceeding with webhook update...
✅ Webhook successfully updated
```

## Safety Features

### Personal Wallet Protection
- Your personal wallet (`DEFAULT_WALLET_ADDRESS`) is **never removed** from the webhook
- It's automatically added if not present
- This ensures you always receive notifications for your own transactions

### Error Handling
- If the sync fails, the system falls back to the existing webhook configuration
- Detailed error messages help you troubleshoot issues
- The webhook continues to function even if sync fails

### Validation
- Addresses are validated before being added to the webhook
- The system checks for duplicate addresses
- Invalid addresses are skipped with warnings

## Troubleshooting

### Common Issues

1. **"HELIUS_API_KEY not found"**
   - Set your Helius API key: `export HELIUS_API_KEY=your_key`

2. **"DEFAULT_WALLET_ADDRESS not found"**
   - Set your personal wallet: `export DEFAULT_WALLET_ADDRESS=your_wallet`

3. **"Could not find our webhook in Helius"**
   - Check that your webhook URL is correct
   - Verify your Helius API key has the correct permissions

4. **"Failed to update webhook"**
   - Check your Helius API key permissions
   - Verify you haven't exceeded your webhook limit
   - Check the Helius dashboard for any errors

### Debug Mode

For detailed logging, you can run the webhook server with debug mode:

```bash
export WEBHOOK_DEBUG_MODE=true
python src/main.py
```

## Integration with CopyBot

The webhook address sync system is fully integrated with the CopyBot agent:

1. **Automatic Sync**: When CopyBot starts, it automatically syncs webhook addresses
2. **Real-time Updates**: Changes to `WALLETS_TO_TRACK` are reflected in the webhook
3. **Seamless Operation**: CopyBot continues to work with the updated wallet list

## Best Practices

1. **Regular Updates**: Update `WALLETS_TO_TRACK` regularly to track the most relevant wallets
2. **Manual Verification**: Use the sync script to verify changes before they take effect
3. **Monitor Logs**: Check webhook logs to ensure addresses are being synced correctly
4. **Backup Configuration**: Keep a backup of your `WALLETS_TO_TRACK` configuration

## API Reference

### Functions

- `sync_webhook_addresses_with_config()`: Main sync function (called automatically)
- `get_current_webhook_addresses()`: Get current addresses from Helius
- `update_webhook_addresses()`: Update webhook with new address list

### Scripts

- `src/scripts/sync_webhook_addresses.py`: Standalone sync script
- `src/scripts/webhook_handler.py`: Integrated sync functionality

## Support

If you encounter issues with the webhook address sync system:

1. Check the troubleshooting section above
2. Review the webhook server logs
3. Verify your environment variables are set correctly
4. Test with the standalone sync script for detailed error messages 