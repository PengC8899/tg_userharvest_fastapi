from __future__ import annotations

import asyncio
from typing import Dict
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError
from .config import get_settings
from .models import Account


_clients: Dict[int, TelegramClient] = {}


async def get_client_for_account(account: Account) -> TelegramClient:
    settings = get_settings()
    client = _clients.get(account.id)
    if client is None:
        client = TelegramClient(StringSession(account.session_string), settings.api_id, settings.api_hash)
        _clients[account.id] = client
    if not client.is_connected():
        await client.connect()
    # ensure authorized
    try:
        if not await client.is_user_authorized():
            # Session string should be authorized; if not, raise
            raise RuntimeError("Session not authorized. Please re-generate StringSession.")
    except FloodWaitError as e:
        await asyncio.sleep(e.seconds + 1)
    return client


async def release_all_clients():
    for c in list(_clients.values()):
        try:
            await c.disconnect()
        except Exception:
            pass
    _clients.clear()