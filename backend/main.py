from fastapi import FastAPI, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer
import requests as req_lib
import contextlib
import uvicorn
from .config import load_tokens, save_tokens, load_config, BASE_DIR
from .bot import manager

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    tokens_data = load_tokens()
    await manager.start_all(tokens_data)
    yield
    await manager.stop_all()

app = FastAPI(lifespan=lifespan)

frontend_dir = BASE_DIR / "frontend"
frontend_dir.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def get_current_user(token: str = Depends(oauth2_scheme)):
    config = load_config()
    if token != config["admin_pass"]:
        raise HTTPException(status_code=401, detail="Invalid token")
    return token

# ─── Pages ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    f = frontend_dir / "index.html"
    return f.read_text(encoding="utf-8") if f.exists() else "Not Found"

@app.get("/login_page", response_class=HTMLResponse)
async def get_login_page():
    f = frontend_dir / "login.html"
    return f.read_text(encoding="utf-8") if f.exists() else "Not Found"

# ─── Auth ─────────────────────────────────────────────────────────────────────

@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    config = load_config()
    if username == config["admin_user"] and password == config["admin_pass"]:
        return {"access_token": password, "token_type": "bearer"}
    raise HTTPException(status_code=400, detail="Incorrect username or password")

# ─── Helpers ──────────────────────────────────────────────────────────────────

def discord_get(path: str, token: str):
    try:
        r = req_lib.get(f"https://discord.com/api/v10{path}", headers={"Authorization": token})
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None

def fetch_discord_profile(token: str):
    return discord_get("/users/@me", token)

def fetch_guild_info(bot_token: str, guild_id: str):
    """Fetch guild name via Discord API using the user token."""
    return discord_get(f"/guilds/{guild_id}?with_counts=false", bot_token)

def fetch_channel_info(bot_token: str, channel_id: str):
    return discord_get(f"/channels/{channel_id}", bot_token)

# ─── Token API ────────────────────────────────────────────────────────────────

@app.get("/api/tokens")
async def api_get_tokens(token: str = Depends(get_current_user)):
    return load_tokens()

@app.post("/api/tokens")
async def api_add_token(data: dict, token: str = Depends(get_current_user)):
    token_str = data.get("token", "").strip()
    if not token_str:
        raise HTTPException(status_code=400, detail="Token is required")

    config = data.get("config", {})

    profile = fetch_discord_profile(token_str)
    if profile:
        config["profile"] = {
            "id": profile.get("id"),
            "username": profile.get("username"),
            "global_name": profile.get("global_name"),
            "discriminator": profile.get("discriminator"),
            "avatar": profile.get("avatar")
        }
    else:
        config["profile"] = None

    tokens_data = load_tokens()
    tokens_data[token_str] = config
    save_tokens(tokens_data)
    await manager.add_token(token_str, config)
    return {"message": "Token added successfully", "profile": config["profile"]}

@app.put("/api/tokens/{token_id:path}")
async def api_update_token(token_id: str, data: dict, token: str = Depends(get_current_user)):
    tokens_data = load_tokens()
    if token_id not in tokens_data:
        raise HTTPException(status_code=404, detail="Token not found")
    # Preserve profile
    if "profile" in tokens_data[token_id] and "profile" not in data:
        data["profile"] = tokens_data[token_id]["profile"]
    tokens_data[token_id] = data
    save_tokens(tokens_data)
    await manager.update_token(token_id, data)
    return {"message": "Token updated"}

@app.post("/api/tokens/{token_id:path}/restart")
async def api_restart_token(token_id: str, token: str = Depends(get_current_user)):
    tokens_data = load_tokens()
    if token_id not in tokens_data:
        raise HTTPException(status_code=404, detail="Token not found")
    await manager.restart_token(token_id)
    return {"message": "Token restarted"}

@app.delete("/api/tokens/{token_id:path}")
async def api_delete_token(token_id: str, token: str = Depends(get_current_user)):
    tokens_data = load_tokens()
    if token_id not in tokens_data:
        raise HTTPException(status_code=404, detail="Token not found")
    del tokens_data[token_id]
    save_tokens(tokens_data)
    await manager.remove_token(token_id)
    return {"message": "Token deleted"}

@app.post("/api/tokens/bulk/status")
async def api_bulk_status(data: dict, token: str = Depends(get_current_user)):
    status = data.get("status", "online")
    tokens_data = load_tokens()
    for t in tokens_data:
        tokens_data[t]["status"] = status
    save_tokens(tokens_data)
    for t in tokens_data:
        await manager.update_token(t, tokens_data[t])
    return {"message": f"All tokens set to {status}"}

@app.post("/api/tokens/bulk/restart")
async def api_bulk_restart(token: str = Depends(get_current_user)):
    tokens_data = load_tokens()
    for t in tokens_data:
        await manager.restart_token(t)
    return {"message": "All tokens restarted"}

@app.post("/api/tokens/bulk/disconnect-vc")
async def api_bulk_disconnect_vc(token: str = Depends(get_current_user)):
    tokens_data = load_tokens()
    for t in tokens_data:
        if "voice" in tokens_data[t]:
            tokens_data[t]["voice"]["channel_id"] = ""
    save_tokens(tokens_data)
    for t in tokens_data:
        await manager.update_token(t, tokens_data[t])
    return {"message": "All tokens disconnected from voice channels"}

# ─── VC API ───────────────────────────────────────────────────────────────────

@app.get("/api/vc-states")
async def api_vc_states(token: str = Depends(get_current_user)):
    tokens_data = load_tokens()
    result = {}
    for t in tokens_data:
        state = manager.get_vc_state(t)
        state = dict(state) if state else {}
        profile = tokens_data[t].get("profile", {}) or {}
        
        # Fallback details fetching if connected
        if state.get("connected"):
            guild_id = state.get("guild_id")
            channel_id = state.get("channel_id")
            
            if guild_id and (not state.get("guild_name") or state.get("guild_name") == guild_id):
                g_info = fetch_guild_info(t, guild_id)
                if g_info:
                    state["guild_name"] = g_info.get("name", guild_id)
                    icon_hash = g_info.get("icon")
                    state["guild_icon"] = f"https://cdn.discordapp.com/icons/{guild_id}/{icon_hash}.png" if icon_hash else None
                    
            if channel_id and (not state.get("channel_name") or state.get("channel_name") == channel_id):
                ch_info = fetch_channel_info(t, channel_id)
                if ch_info:
                    state["channel_name"] = ch_info.get("name", channel_id)
                    
        result[t] = {
            "profile": profile,
            "vc_state": state
        }
    return result

@app.post("/api/vc/join")
async def api_vc_join(data: dict, token: str = Depends(get_current_user)):
    token_str = data.get("token")
    guild_id = data.get("guild_id", "").strip()
    channel_id = data.get("channel_id", "").strip()
    self_mute = data.get("self_mute", True)
    self_deaf = data.get("self_deaf", False)

    if not token_str or not guild_id or not channel_id:
        raise HTTPException(status_code=400, detail="token, guild_id, channel_id required")

    tokens_data = load_tokens()
    if token_str not in tokens_data:
        raise HTTPException(status_code=404, detail="Token not found")

    config = tokens_data[token_str]
    config["voice"] = {
        "guild_id": guild_id,
        "channel_id": channel_id,
        "self_mute": self_mute,
        "self_deaf": self_deaf
    }
    tokens_data[token_str] = config
    save_tokens(tokens_data)
    await manager.update_token(token_str, config)
    return {"message": "Join command sent"}

@app.post("/api/vc/disconnect")
async def api_vc_disconnect(data: dict, token: str = Depends(get_current_user)):
    token_str = data.get("token")
    guild_id = data.get("guild_id", "").strip()

    if not token_str:
        raise HTTPException(status_code=400, detail="token required")

    tokens_data = load_tokens()
    if token_str not in tokens_data:
        raise HTTPException(status_code=404, detail="Token not found")

    config = tokens_data[token_str]
    config["voice"] = {
        "guild_id": guild_id,
        "channel_id": "",
        "self_mute": True,
        "self_deaf": False
    }
    tokens_data[token_str] = config
    save_tokens(tokens_data)
    await manager.update_token(token_str, config)
    return {"message": "Disconnect command sent"}

# ─── Lookup helpers for frontend ──────────────────────────────────────────────

@app.get("/api/lookup/guild/{token_id:path}/{guild_id}")
async def api_lookup_guild(token_id: str, guild_id: str, token: str = Depends(get_current_user)):
    """Use the user's own token to look up a guild name."""
    info = fetch_guild_info(token_id, guild_id)
    if not info:
        return {"name": guild_id, "icon": None}
    icon_hash = info.get("icon")
    icon_url = f"https://cdn.discordapp.com/icons/{guild_id}/{icon_hash}.png" if icon_hash else None
    return {"name": info.get("name", guild_id), "icon": icon_url}

@app.get("/api/lookup/channel/{token_id:path}/{channel_id}")
async def api_lookup_channel(token_id: str, channel_id: str, token: str = Depends(get_current_user)):
    info = fetch_channel_info(token_id, channel_id)
    if not info:
        return {"name": channel_id}
    return {"name": info.get("name", channel_id)}

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
