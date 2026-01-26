Get your SendGrid webhook URL (for Inbound Parse)
================================================

1. Start igwe so it is listening on port 8000 (e.g. run main.py).

2. Start ngrok in a separate terminal:
   "C:\Users\Top Cash Pawn\ITORO\agent-systems\itoro\ngrok.exe" http 8000
   (Or from that folder: ngrok.exe http 8000)

3. In another terminal, from the igwe folder run:
   python scripts/get_webhook_url.py

4. Copy the printed URL and paste it into SendGrid:
   Inbound Parse → Add Host & URL → Destination URL

5. In .env set:
   SENDGRID_REPLY_TO=replies@reimaginewealth.org
   (So lead replies go to replies@ → SendGrid → your app.)
