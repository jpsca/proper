import asyncio
import typing as t

from ..helpers import jsonplus, logger
from ..types import TReceive, TScope, TSend


if t.TYPE_CHECKING:
    from ..app import App
    from ..channels import Channel
    from ..router import Router


def _subscription_key(channel_name: str, params: dict) -> str:
    sorted_params = sorted(params.items())
    return f"{channel_name}:{sorted_params}"


def _enqueue_send(loop, ws_send, msg):
    loop.call_soon_threadsafe(asyncio.ensure_future, ws_send(msg))


class AppWs:
    """A Mixin for WebSocket support in Proper apps
    """
    config: dict
    router: "Router"

    def _with_db(self, work, *, on_error=None) -> None:
        ...

    async def _handle_websocket(
        self,
        scope: TScope,
        receive: TReceive,
        send: TSend,
    ) -> None:
        path = scope.get("path", "")
        cable_path = self.config.get("CABLE_PATH", "/cable")
        if path != cable_path:
            await send({"type": "websocket.close", "code": 4004})
            return

        await send({"type": "websocket.accept"})
        subscriptions: dict[str, "Channel"] = {}

        async def ws_send(msg: dict) -> None:
            await send({
                "type": "websocket.send",
                "text": jsonplus.dumps(msg),
            })

        try:
            while True:
                event = await receive()
                if event["type"] == "websocket.disconnect":
                    break

                if event["type"] != "websocket.receive":
                    continue

                text = event.get("text", "")
                if not text:
                    continue

                try:
                    msg = jsonplus.loads(text)
                except Exception:
                    await ws_send({"type": "error", "reason": "invalid_json"})
                    continue

                command = msg.get("command")
                channel_name = msg.get("channel", "")
                params = msg.get("params") or {}

                sub_key = _subscription_key(channel_name, params)

                if command == "subscribe":
                    await self._ws_subscribe(
                        channel_name, params, sub_key,
                        subscriptions, ws_send,
                    )
                elif command == "unsubscribe":
                    await self._ws_unsubscribe(
                        sub_key, subscriptions, ws_send,
                    )
                elif command == "message":
                    await self._ws_message(
                        msg, sub_key, subscriptions, ws_send,
                    )
                else:
                    await ws_send({
                        "type": "error",
                        "reason": "unknown_command",
                    })
        finally:
            for channel in subscriptions.values():
                try:
                    channel.stop_all_streams()
                    await asyncio.to_thread(
                        self._with_db,
                        lambda ch=channel: ch._dispatch("unsubscribed"),
                    )
                except Exception:
                    logger.exception(
                        "Error in %s.unsubscribed", channel.channel_name,
                    )
            subscriptions.clear()

    async def _ws_subscribe(
        self,
        channel_name: str,
        params: dict,
        sub_key: str,
        subscriptions: dict[str, "Channel"],
        ws_send,
    ) -> None:
        channel_cls = self.router.channels.get(channel_name)
        if not channel_cls:
            await ws_send({
                "type": "reject_subscription",
                "channel": channel_name,
                "params": params,
                "reason": "unknown_channel",
            })
            return

        pending: list[dict] = []

        def sync_send(msg):
            pending.append(msg)

        channel = channel_cls(t.cast("App", self), params, _send=sync_send)
        await asyncio.to_thread(
            self._with_db,
            lambda: channel._dispatch("subscribed"),
        )

        if channel._rejected:
            await ws_send({
                "type": "reject_subscription",
                "channel": channel_name,
                "params": params,
            })
            return

        subscriptions[sub_key] = channel

        # Flush any messages sent during subscribed()
        for msg in pending:
            await ws_send(msg)

        # Now wire up the real async send (thread-safe)
        # This enqueues async sends from sync
        loop = asyncio.get_running_loop()
        channel._send = lambda msg: _enqueue_send(loop, ws_send, msg)

        await ws_send({
            "type": "confirm_subscription",
            "channel": channel_name,
            "params": params,
        })

    async def _ws_unsubscribe(
        self,
        sub_key: str,
        subscriptions: dict[str, "Channel"],
        ws_send,
    ) -> None:
        channel = subscriptions.pop(sub_key, None)
        if channel:
            channel.stop_all_streams()
            await asyncio.to_thread(
                self._with_db,
                lambda: channel._dispatch("unsubscribed"),
            )

    async def _ws_message(
        self,
        msg: dict,
        sub_key: str,
        subscriptions: dict[str, "Channel"],
        ws_send,
    ) -> None:
        channel = subscriptions.get(sub_key)
        if not channel:
            await ws_send({
                "type": "error",
                "reason": "not_subscribed",
            })
            return

        action = msg.get("action", "")
        _blocked = (
            "subscribed", "unsubscribed",
            "send", "broadcast", "reject",
            "stream_from", "stop_stream_from", "stop_all_streams",
        )
        if not action or action.startswith("_") or action in _blocked:
            await ws_send({
                "type": "error",
                "reason": "invalid_action",
            })
            return

        if not hasattr(channel, action) or not callable(getattr(channel, action)):
            await ws_send({
                "type": "error",
                "reason": "unknown_action",
            })
            return

        data = msg.get("data") or {}
        await asyncio.to_thread(
            self._with_db,
            lambda: channel._dispatch(action, data),
        )
