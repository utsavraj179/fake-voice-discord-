import asyncio
import contextlib
import json
import logging
import time
import aiohttp
from typing import Dict, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bot")


def resolve_image(value: str) -> str:
    """
    Fallback helper (deprecated, use DiscordClient.resolve_asset)
    """
    if not value:
        return value
    v = value.strip()
    if v.startswith("http://") or v.startswith("https://"):
        return f"mp:external/{v}"
    return v


class DiscordClient:
    def __init__(self, token: str, config: dict):
        self.token = token
        self.config = config
        self.ws = None
        self.heartbeat_task = None
        self._start_task: Optional[asyncio.Task] = None
        self.running = False
        self.session = None
        # Track when this client first connected (for elapsed timestamps)
        self._internal_start_time = int(time.time())
        # Voice state tracking
        self.vc_state: dict = {}   # {"guild_id": ..., "channel_id": ..., "guild_name": ..., "channel_name": ...}
        self._guild_cache: Dict[str, dict] = {}

    async def get_app_assets(self, app_id: str) -> list:
        if not hasattr(self, "_app_assets_cache"):
            self._app_assets_cache = {}
        if app_id in self._app_assets_cache:
            return self._app_assets_cache[app_id]
        if not self.session or self.session.closed:
            return []
        headers = {"Authorization": self.token}
        url = f"https://discord.com/api/v10/oauth2/applications/{app_id}/assets"
        try:
            async with self.session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    assets = await resp.json()
                    self._app_assets_cache[app_id] = assets
                    return assets
        except Exception as e:
            logger.error(f"Error fetching app assets: {e}")
        return []

    def resolve_asset(self, value: str, assets_list: list) -> str:
        if not value:
            return value
        v = value.strip()
        if v.startswith("http://") or v.startswith("https://"):
            return f"mp:external/{v}"
        for asset in assets_list:
            if asset.get("name") == v:
                return asset.get("id")
        return v

    async def start(self):
        self.running = True
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession()
        while self.running:
            try:
                await self.connect()
            except asyncio.CancelledError:
                break
            except Exception as e:
                if not self.running:
                    break
                logger.error(f"[{self.token[:10]}...] Connection error: {e}")
                if self.running:
                    await asyncio.sleep(5)

    async def stop(self):
        self.running = False
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            self.heartbeat_task = None
        if self.ws and not self.ws.closed:
            try:
                await self.ws.close()
            except Exception:
                pass
        if self.session and not self.session.closed:
            try:
                await self.session.close()
            except Exception:
                pass
        self.ws = None
        self.session = None

    async def connect(self):
        uri = "wss://gateway.discord.gg/?v=10&encoding=json"
        async with self.session.ws_connect(uri) as ws:
            self.ws = ws
            hello = await ws.receive_json()
            heartbeat_interval = hello["d"]["heartbeat_interval"]

            if self.heartbeat_task:
                self.heartbeat_task.cancel()
            self.heartbeat_task = asyncio.create_task(self.heartbeat(heartbeat_interval))

            await self.identify()

            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    t = data.get("t")
                    if t == "READY":
                        logger.info(f"[{self.token[:10]}...] Ready!")
                        await self.update_presence()
                        await self.update_voice()
                    elif t == "VOICE_STATE_UPDATE":
                        await self._handle_voice_state(data.get("d", {}))
                    elif t == "GUILD_CREATE":
                        # Cache guild/channel names for VC tracking
                        self._cache_guild(data.get("d", {}))
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    break

    def _cache_guild(self, guild_data: dict):
        guild_id = guild_data.get("id")
        if not guild_id:
            return
        channels = {}
        for ch in guild_data.get("channels", []):
            channels[ch["id"]] = ch.get("name", ch["id"])
        icon_hash = guild_data.get("icon")
        icon_url = f"https://cdn.discordapp.com/icons/{guild_id}/{icon_hash}.png" if icon_hash else None
        self._guild_cache[guild_id] = {
            "name": guild_data.get("name", guild_id),
            "icon_url": icon_url,
            "channels": channels
        }

    async def _handle_voice_state(self, d: dict):
        # Only care about our own user
        # We can't easily get our own ID here without storing it at READY.
        # Instead we just check if session_id matches or channel_id is present.
        # We'll update vc_state whenever we get any VOICE_STATE_UPDATE with a channel.
        guild_id = d.get("guild_id")
        channel_id = d.get("channel_id")
        if channel_id:
            guild_info = self._guild_cache.get(guild_id, {})
            self.vc_state = {
                "guild_id": guild_id,
                "channel_id": channel_id,
                "guild_name": guild_info.get("name", guild_id),
                "guild_icon": guild_info.get("icon_url"),
                "channel_name": guild_info.get("channels", {}).get(channel_id, channel_id),
                "connected": True
            }
        else:
            self.vc_state = {"connected": False, "guild_id": guild_id}

    # ─── Heartbeat ─────────────────────────────────────────────────────────────
    async def heartbeat(self, interval):
        while self.running:
            await asyncio.sleep(interval / 1000)
            if self.ws and not self.ws.closed:
                try:
                    await self.ws.send_json({"op": 1, "d": None})
                except Exception as e:
                    logger.error(f"Heartbeat failed: {e}")
                    break

    # ─── Identify ──────────────────────────────────────────────────────────────
    async def identify(self):
        platform = self.config.get("platform", "pc")
        browser = "Discord iOS" if platform == "mobile" else "chrome"
        os_name = "ios" if platform == "mobile" else "windows"
        device = "iPhone" if platform == "mobile" else "pc"

        payload = {
            "op": 2,
            "d": {
                "token": self.token,
                "intents": 0,
                "properties": {
                    "$os": os_name,
                    "$browser": browser,
                    "$device": device
                }
            }
        }
        await self.ws.send_json(payload)

    # ─── Presence ──────────────────────────────────────────────────────────────
    async def update_presence(self):
        if not self.ws or self.ws.closed:
            return

        status = self.config.get("status", "online")
        status_text = self.config.get("status_text", "")
        rpc = self.config.get("rpc", {})

        activities = []

        # Custom Status Text (type 4)
        if status_text:
            activities.append({
                "type": 4,
                "name": "Custom Status",
                "state": status_text
            })

        # Rich Presence
        if rpc and rpc.get("name"):
            activity_type_map = {
                "playing": 0,
                "streaming": 1,
                "listening": 2,
                "watching": 3
            }
            act_type_str = rpc.get("activity_type", "playing").lower()
            act_type = activity_type_map.get(act_type_str, 0)

            activity = {
                "type": act_type,
                "name": rpc.get("name", "Playing"),
            }

            # Application ID only required for image assets
            if rpc.get("application_id"):
                activity["application_id"] = rpc.get("application_id")

            if rpc.get("details"):
                activity["details"] = rpc["details"]
            if rpc.get("state"):
                activity["state"] = rpc["state"]

            # Streaming URL
            if act_type == 1 and rpc.get("url"):
                activity["url"] = rpc.get("url")

            # ── Timestamps ──────────────────────────────────────────────
            timestamps = {}
            ts_start_raw = str(rpc.get("timestamp_start", "")).strip()
            ts_end_raw = str(rpc.get("timestamp_end", "")).strip()

            if ts_start_raw.lower() in ("auto", "true"):
                timestamps["start"] = self._internal_start_time
            elif ts_start_raw:
                try:
                    timestamps["start"] = int(float(ts_start_raw))
                except (ValueError, TypeError):
                    pass

            if ts_end_raw:
                try:
                    timestamps["end"] = int(float(ts_end_raw))
                except (ValueError, TypeError):
                    pass

            if timestamps:
                activity["timestamps"] = timestamps

            # Fetch assets if application_id is provided
            app_id = rpc.get("application_id", "").strip()
            assets_list = []
            if app_id:
                assets_list = await self.get_app_assets(app_id)

            # ── Assets (images) ─────────────────────────────────────────
            assets = {}
            large_img = self.resolve_asset(rpc.get("large_image", ""), assets_list)
            if large_img:
                assets["large_image"] = large_img
            if rpc.get("large_text"):
                assets["large_text"] = rpc["large_text"]
            small_img = self.resolve_asset(rpc.get("small_image", ""), assets_list)
            if small_img:
                assets["small_image"] = small_img
            if rpc.get("small_text"):
                assets["small_text"] = rpc["small_text"]

            if assets:
                activity["assets"] = assets

            # ── Buttons (metadata format for user gateway RPC) ──────────
            button_labels = []
            button_urls = []
            for i in [1, 2]:
                lbl = rpc.get(f"btn{i}_label", "").strip()
                url = rpc.get(f"btn{i}_url", "").strip()
                if lbl and url:
                    if not url.startswith(("http://", "https://")):
                        url = f"https://{url}"
                    button_labels.append(lbl[:32])
                    button_urls.append(url[:512])

            if button_labels and button_urls:
                if not app_id:
                    logger.warning(f"[{self.token[:10]}...] RPC buttons need application_id — skipping buttons")
                else:
                    activity["metadata"] = json.dumps({
                        "button_urls": button_urls,
                        "button_labels": button_labels
                    })

            activities.append(activity)

        payload = {
            "op": 3,
            "d": {
                "since": 0,
                "activities": activities,
                "status": status,
                "afk": status == "idle"
            }
        }
        await self.ws.send_json(payload)

    # ─── Voice ─────────────────────────────────────────────────────────────────
    async def update_voice(self):
        if not self.ws or self.ws.closed:
            return

        voice = self.config.get("voice", {})
        guild_id = voice.get("guild_id", "").strip()
        channel_id = voice.get("channel_id", "").strip()

        if guild_id:
            payload = {
                "op": 4,
                "d": {
                    "guild_id": guild_id,
                    "channel_id": channel_id if channel_id else None,
                    "self_mute": voice.get("self_mute", True),
                    "self_deaf": voice.get("self_deaf", False)
                }
            }
            await self.ws.send_json(payload)


# ─── Token Manager ─────────────────────────────────────────────────────────────

class TokenManager:
    def __init__(self):
        self.clients: Dict[str, DiscordClient] = {}

    async def start_all(self, tokens_data: dict):
        for token, config in tokens_data.items():
            await self.add_token(token, config)

    def _launch_client(self, client: DiscordClient):
        client._start_task = asyncio.create_task(client.start())

    async def add_token(self, token: str, config: dict):
        if token in self.clients:
            await self.update_token(token, config)
            return
        client = DiscordClient(token, config)
        self.clients[token] = client
        self._launch_client(client)

    async def update_token(self, token: str, config: dict):
        if token not in self.clients:
            return
        client = self.clients[token]
        old_platform = client.config.get("platform", "pc")
        new_platform = config.get("platform", "pc")
        client.config = config
        if old_platform != new_platform:
            await client.stop()
            if client._start_task and not client._start_task.done():
                client._start_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await client._start_task
            new_client = DiscordClient(token, config)
            self.clients[token] = new_client
            self._launch_client(new_client)
        else:
            await client.update_presence()
            await client.update_voice()

    async def restart_token(self, token: str):
        if token not in self.clients:
            return
        client = self.clients[token]
        config = client.config
        await client.stop()
        if client._start_task and not client._start_task.done():
            client._start_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await client._start_task
        new_client = DiscordClient(token, config)
        new_client._internal_start_time = int(time.time())
        self.clients[token] = new_client
        self._launch_client(new_client)

    async def remove_token(self, token: str):
        if token in self.clients:
            client = self.clients.pop(token)
            await client.stop()
            if client._start_task and not client._start_task.done():
                client._start_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await client._start_task

    def get_vc_state(self, token: str) -> dict:
        if token in self.clients:
            return self.clients[token].vc_state
        return {}

    async def stop_all(self):
        for client in list(self.clients.values()):
            await client.stop()
        self.clients.clear()


manager = TokenManager()
