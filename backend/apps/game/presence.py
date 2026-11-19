"""Lobby presence tracking, duplicate-tab eviction, and 30-second disconnect grace timers."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from uuid import UUID

import redis.asyncio as aioredis
from django.conf import settings


class PresenceManager:
    """Manage active WebSocket channels, lobby presence, and disconnect grace timers."""

    def __init__(self) -> None:
        self._active_channels: dict[tuple[str, str], str] = {}
        self._present_players: dict[str, set[str]] = {}
        self._grace_tasks: dict[tuple[str, str], asyncio.Task[None]] = {}
        self._redis_client: aioredis.Redis | None = None

    def _get_redis(self) -> aioredis.Redis | None:
        redis_url = getattr(settings, "REDIS_URL", "")
        if not redis_url:
            return None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if self._redis_client is not None:
            pool = getattr(self._redis_client, "connection_pool", None)
            pool_loop = getattr(pool, "_loop", None)
            if pool_loop is not None and (
                pool_loop.is_closed() or (loop is not None and pool_loop is not loop)
            ):
                self._redis_client = None

        if self._redis_client is None:
            self._redis_client = aioredis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=5.0,
                socket_timeout=5.0,
                retry_on_timeout=True,
                health_check_interval=30,
            )
        return self._redis_client

    async def close(self) -> None:
        """Close shared Redis client connection pool."""
        if self._redis_client is not None:
            await self._redis_client.aclose()
            self._redis_client = None

    @staticmethod
    def _active_key(room_code: str, player_id: str) -> str:
        return f"stb:ws:active:{room_code}:{player_id}"

    @staticmethod
    def _present_key(room_code: str) -> str:
        return f"stb:ws:present:{room_code}"

    async def register_connection(
        self,
        room_code: str,
        player_id: UUID,
        channel_name: str,
    ) -> str | None:
        """Record active channel for player and return any previous channel to evict."""
        pid = str(player_id)
        self.cancel_grace_timer(room_code, player_id)

        client = self._get_redis()
        if client is not None:
            key = self._active_key(room_code, pid)
            previous = await client.getset(key, channel_name)
            await client.expire(key, 86_400)
            return str(previous) if previous and previous != channel_name else None

        pair = (room_code, pid)
        previous = self._active_channels.get(pair)
        self._active_channels[pair] = channel_name
        return previous if previous and previous != channel_name else None

    async def clear_connection_if_current(
        self,
        room_code: str,
        player_id: UUID,
        channel_name: str,
    ) -> bool:
        """Clear active channel only if channel_name is still the current one."""
        pid = str(player_id)
        client = self._get_redis()
        if client is not None:
            key = self._active_key(room_code, pid)
            current = await client.get(key)
            if current != channel_name:
                return False
            await client.delete(key)
            return True

        pair = (room_code, pid)
        if self._active_channels.get(pair) != channel_name:
            return False
        self._active_channels.pop(pair, None)
        return True

    async def mark_present(self, room_code: str, player_id: UUID) -> bool:
        """Mark player present in lobby; return True if already present before this call."""
        pid = str(player_id)
        client = self._get_redis()
        if client is not None:
            key = self._present_key(room_code)
            added = await client.sadd(key, pid)
            await client.expire(key, 86_400)
            return added == 0

        members = self._present_players.setdefault(room_code, set())
        was_present = pid in members
        members.add(pid)
        return was_present

    async def clear_present(self, room_code: str, player_id: UUID) -> bool:
        """Remove player from active presence set; return True if removed."""
        pid = str(player_id)
        client = self._get_redis()
        if client is not None:
            removed = await client.srem(self._present_key(room_code), pid)
            return removed > 0

        members = self._present_players.get(room_code)
        if not members or pid not in members:
            return False
        members.remove(pid)
        return True

    async def get_present_ids(self, room_code: str) -> set[str]:
        """Return the set of player UUID strings currently present in the room."""
        client = self._get_redis()
        if client is not None:
            members = await client.smembers(self._present_key(room_code))
            return {str(member) for member in members}

        return set(self._present_players.get(room_code, set()))

    def cancel_grace_timer(self, room_code: str, player_id: UUID) -> None:
        """Cancel a pending disconnect grace task for (room_code, player_id)."""
        pair = (room_code, str(player_id))
        task = self._grace_tasks.pop(pair, None)
        if task is not None and not task.done():
            task.cancel()

    def schedule_grace_timer(
        self,
        room_code: str,
        player_id: UUID,
        on_expire: Callable[[], Awaitable[None]],
    ) -> None:
        """Schedule grace expiration callback after PRESENCE_GRACE_SECONDS."""
        self.cancel_grace_timer(room_code, player_id)
        grace_seconds = float(getattr(settings, "PRESENCE_GRACE_SECONDS", 30.0))
        pair = (room_code, str(player_id))

        async def _runner() -> None:
            try:
                await asyncio.sleep(grace_seconds)
                await on_expire()
            except asyncio.CancelledError:
                return
            finally:
                current = self._grace_tasks.get(pair)
                if current is asyncio.current_task():
                    self._grace_tasks.pop(pair, None)

        self._grace_tasks[pair] = asyncio.create_task(_runner())

    async def reset_all(self) -> None:
        """Cancel all grace timers and clear presence/active channel state (for test cleanup)."""
        tasks = list(self._grace_tasks.values())
        self._grace_tasks.clear()
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._active_channels.clear()
        self._present_players.clear()

        client = self._get_redis()
        if client is not None:
            keys = [key async for key in client.scan_iter(match="stb:ws:*")]
            if keys:
                await client.delete(*keys)
        await self.close()


presence_manager = PresenceManager()
