import asyncio
import threading
import typing as t

from ..channels.cable import CABLE_SALT, FORWARD_MAX_AGE
from ..helpers import jsonplus, logger


if t.TYPE_CHECKING:
    from ..app import App
    from ..channels import Cable, Channel
    from ..router import Router
    from .request import Request

# RSGI WebSocket message kinds.
WS_CLOSE = 0
WS_BYTES = 1
WS_TEXT = 2


# Put on the outbox to tell the writer there is nothing more to send.
_CLOSE = object()


def _subscription_key(channel_name: str, params: dict) -> str:
    sorted_params = sorted(params.items())
    return f"{channel_name}:{sorted_params}"


class AppWs:
    """A Mixin for WebSocket support in Proper apps
    """
    config: dict
    router: "Router"
    cable: "Cable"

    max_threads: int

    if t.TYPE_CHECKING:
        def _with_db(self, work, *, on_error=None) -> None: ...

        async def _run_in_worker(self, func, *args) -> t.Any: ...

        def _request_from_scope(self, scope) -> "Request": ...

    async def _receive_broadcast(self: "App", scope, protocol) -> None:
        """A broadcast forwarded by a process without WebSockets, as a
        `POST` to `CABLE_PATH`: a token signed with the app's keys, carrying
        the stream and the data. Anything else gets a 403; behind a proxy
        this path is reachable from outside."""
        token = (await protocol()).decode("utf-8", "replace")
        payload = self.loads(token, salt=CABLE_SALT, max_age=FORWARD_MAX_AGE)
        if not isinstance(payload, dict) or "stream" not in payload:
            logger.warning("[cable] refused a broadcast with a bad signature")
            protocol.response_empty(403, [])
            return
        self.cable._deliver_local(payload["stream"], payload.get("data"))
        protocol.response_empty(204, [])

    async def _handle_websocket(self, scope, protocol) -> None:
        cable_path = self.config.get("CABLE_PATH", "/cable")
        if scope.path != cable_path:
            # Before the handshake is accepted this is still HTTP, so the
            # refusal is an HTTP status, not a WebSocket close code.
            protocol.close(404)
            return

        transport = await protocol.accept()
        # The handshake's headers and cookies, for channels to authenticate
        # the connection with.
        request = self._request_from_scope(scope)
        subscriptions: dict[str, "Channel"] = {}

        # Everything going out to this client passes through one queue,
        # drained by one task. Channels run in worker threads and hand their
        # messages over with `call_soon_threadsafe`, so a single consumer is
        # what keeps them in the order they were sent.
        outbox: asyncio.Queue = asyncio.Queue()

        async def ws_send(msg: dict) -> None:
            await outbox.put(msg)

        async def writer() -> None:
            while True:
                msg = await outbox.get()
                if msg is _CLOSE:
                    return
                try:
                    await transport.send_str(jsonplus.dumps(msg))
                except Exception:
                    # The connection is gone. The receive loop below sees
                    # the disconnect and takes care of the cleanup.
                    logger.exception("[cable] could not send to the client")
                    return

        writer_task = asyncio.create_task(writer())

        try:
            while True:
                try:
                    message = await transport.receive()
                except Exception:
                    # The connection dropped without a close frame.
                    break
                if message.kind == WS_CLOSE:
                    break
                if message.kind != WS_TEXT:
                    continue

                text = message.data
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
                        channel_name=channel_name,
                        params=params,
                        sub_key=sub_key,
                        subscriptions=subscriptions,
                        ws_send=ws_send,
                        outbox=outbox,
                        request=request,
                    )
                elif command == "unsubscribe":
                    await self._ws_unsubscribe(
                        sub_key=sub_key,
                        subscriptions=subscriptions,
                        ws_send=ws_send,
                    )
                elif command == "message":
                    await self._ws_message(
                        msg=msg,
                        sub_key=sub_key,
                        subscriptions=subscriptions,
                        ws_send=ws_send,
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
                    await self._run_in_worker(
                        self._with_db,
                        lambda ch=channel: ch._dispatch("unsubscribed"),
                    )
                except Exception:
                    logger.exception(
                        "Error in %s.unsubscribed", channel.channel_name,
                    )
            subscriptions.clear()
            # Let whatever is already queued reach the client before
            # closing, then make sure the writer is not left behind.
            outbox.put_nowait(_CLOSE)
            try:
                await writer_task
            finally:
                writer_task.cancel()

    async def _ws_subscribe(
        self,
        channel_name: str,
        params: dict,
        sub_key: str,
        subscriptions: dict[str, "Channel"],
        ws_send,
        outbox: asyncio.Queue,
        request: "Request",
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

        loop = asyncio.get_running_loop()
        # Until the subscription is accepted, messages are held back rather
        # than sent: `subscribed()` may still reject, and a rejected channel
        # must not reach the client. `pending` becomes `None` once that is
        # settled, and everything goes straight to the outbox from then on.
        # The lock is what makes the handover atomic for the worker thread
        # `subscribed()` runs in, and for any thread broadcasting to a stream
        # it just opened.
        pending: list[dict] | None = []
        handover = threading.Lock()

        def sync_send(msg):
            with handover:
                if pending is not None:
                    pending.append(msg)
                    return
            loop.call_soon_threadsafe(outbox.put_nowait, msg)

        channel = channel_cls(
            t.cast("App", self),
            params,
            request=request,
            _send=sync_send,
        )
        await self._run_in_worker(
            self._with_db,
            lambda: channel._dispatch("subscribed"),
        )

        if channel._rejected:
            # `subscribed()` may have opened streams before deciding to
            # reject. Nothing else would ever close them: the channel is
            # not in `subscriptions`, so the cleanup on disconnect misses it.
            channel.stop_all_streams()
            await ws_send({
                "type": "reject_subscription",
                "channel": channel_name,
                "params": params,
            })
            return

        subscriptions[sub_key] = channel

        # Release whatever `subscribed()` sent, and let later messages
        # through. Both happen under the lock so nothing overtakes them.
        with handover:
            for msg in pending:
                outbox.put_nowait(msg)
            pending = None

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
            await self._run_in_worker(
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
        await self._run_in_worker(
            self._with_db,
            lambda: channel._dispatch(action, data),
        )
