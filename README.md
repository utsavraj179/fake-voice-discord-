# Voicecord

Discord voice channel & Rich Presence manager with a web dashboard. Keep accounts online, set custom status/RPC, and join voice channels automatically.

---

## Features

- Web dashboard (Discord-style dark blue/black UI)
- Multiple Discord token management
- Custom status (Online / Idle / DND)
- Rich Presence (RPC) with images, timestamps & buttons
- Voice channel join/disconnect (manual + auto-join)
- Bulk operations (restart all, set status, disconnect all VCs)
- PC & Mobile platform spoofing

---

## Requirements

- **Python 3.10+**
- Discord user token(s)
- Server (Guild) ID & Voice Channel ID (for voice features)
- Application ID from [Discord Developer Portal](https://discord.com/developers/applications) (required for RPC buttons)

---

## Local Setup & Testing

### Step 1 — Clone & install

```bash
git clone <your-repo-url>
cd Voicecord-main
pip install -r requirements.txt
```

### Step 2 — Configure admin login

Edit `config.json` (auto-created on first run if missing):

```json
{
    "admin_user": "admin",
    "admin_pass": "your_secure_password"
}
```

### Step 3 — Start the server

```bash
python run.py
```

Server starts at: **http://localhost:8000**

### Step 4 — Login & add token

1. Open **http://localhost:8000** in your browser
2. Login with your `config.json` credentials
3. Click **+ New Token** and paste your Discord user token
4. Configure status, RPC, and voice settings
5. Click **Save**

### Step 5 — Test voice channels

1. Go to **Voice Channels** tab
2. Enter **Server ID** and **Channel ID**
3. Click **Join**
4. Check Discord — account should appear in the voice channel

### Step 6 — Test RPC with buttons

1. Edit a token → set **Activity Name** (e.g. `Minecraft`)
2. Set **Application ID** (your Discord app's Client ID)
3. Add button label + URL (must start with `https://`)
4. Save — RPC should stay active with buttons visible to other users

> **Note:** You cannot see your own RPC buttons. Ask a friend or use a second account to verify.

---

## Standalone Script (No Web UI)

Edit `main.py` with your token, guild ID, and channel ID:

```python
TOKEN = "your_discord_token"
GUILD_ID = "your_server_id"
CHANNEL_ID = "your_voice_channel_id"
```

Run:

```bash
python main.py
```

---

## Deploy on Railway

### Step 1 — Push to GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/voicecord.git
git push -u origin main
```

### Step 2 — Create Railway project

1. Go to [railway.app](https://railway.app) and sign in
2. Click **New Project** → **Deploy from GitHub repo**
3. Select your Voicecord repository
4. Railway auto-detects Python and uses the `Procfile`

### Step 3 — Set environment variables

In Railway → your service → **Variables**, add:

| Variable | Value | Required |
|----------|-------|----------|
| `ADMIN_USER` | Your dashboard username | Yes |
| `ADMIN_PASS` | Your dashboard password | Yes |
| `PORT` | Auto-set by Railway | Auto |

Example:

```
ADMIN_USER=admin
ADMIN_PASS=MySecurePass123!
```

### Step 4 — Add persistent storage (important!)

Railway's filesystem is **ephemeral** — tokens are lost on every redeploy unless you add a volume.

1. In Railway → your service → **Settings**
2. Scroll to **Volumes** → **Add Volume**
3. Mount path: `/app`
4. This keeps `tokens.json` and `config.json` across restarts

Without a volume, you must re-add tokens after each deploy.

### Step 5 — Generate public URL

1. Go to **Settings** → **Networking**
2. Click **Generate Domain**
3. Your app will be live at: `https://your-app.up.railway.app`

### Step 6 — Verify deployment

1. Open your Railway URL
2. Login with `ADMIN_USER` / `ADMIN_PASS`
3. Add a token and test

---

## Railway Troubleshooting

| Problem | Solution |
|---------|----------|
| App crashes on start | Check Railway logs; ensure `requirements.txt` is present |
| Login fails | Verify `ADMIN_USER` and `ADMIN_PASS` env vars are set |
| Tokens disappear after redeploy | Add a Railway Volume mounted at `/app` |
| RPC buttons not showing | Set Application ID + Activity Name; URLs must be `https://` |
| Voice join fails | Double-check Guild ID and Channel ID are correct |
| Port error | Railway sets `PORT` automatically — don't hardcode 8000 |

---

## File Structure

```
Voicecord-main/
├── backend/
│   ├── main.py        # FastAPI server & API routes
│   ├── bot.py         # Discord gateway client
│   └── config.py      # Config & token file helpers
├── frontend/
│   ├── index.html     # Dashboard UI
│   ├── login.html     # Login page
│   ├── app.js         # Frontend logic
│   └── style.css      # Discord-style theme
├── config.json        # Admin credentials (local)
├── tokens.json        # Saved Discord tokens (auto-created)
├── run.py             # Local server entry point
├── Procfile           # Railway/Heroku start command
├── railway.toml       # Railway deploy config
├── requirements.txt   # Python dependencies
└── main.py            # Standalone voice script
```

---

## Configuration Reference

### config.json (local)

```json
{
    "admin_user": "admin",
    "admin_pass": "admin123"
}
```

### tokens.json (auto-managed)

Stores Discord tokens and their settings. Do not share this file.

### Environment variables (Railway/production)

```
ADMIN_USER=your_username
ADMIN_PASS=your_password
PORT=8000
```

---

## Security Notes

- Change the default password before exposing on any network
- Never commit `tokens.json` to Git (already in `.gitignore`)
- Use Railway environment variables for production credentials
- Using self-bots violates Discord Terms of Service — use at your own risk

---

## License

MIT — use freely, no warranty.

## Developer
Offical Dev: SUBHAN
Discord Server: https://dsc.gg/hexacordoffical
Discrod Username: .subhan.exe
Discord ID: 1262027340129505290
