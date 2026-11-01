---
title: Channels
description: Channels addon, server side: defining channels, lifecycle, actions and replies, streams, broadcasting and presence, authentication, debugging, testing
last_verified: 2026-11-01
sources:
  - src/proper/channels
  - src/proper/tools/cable.py
  - src/proper/_blueprints/addon_channels
---

# Channels

Proper Channels is an installable addon that provides a channel-based WebSocket system for real-time communication. All WebSocket traffic of a page is multiplexed over one connection, served on `CABLE_PORT` (behind the proxy, at `CABLE_PATH`, `/cable` by default). Clients subscribe to named channels, and channels can broadcast messages to all subscribers of a stream.

The system has three layers:

| Layer        | Module                  | Role                                                          |
|--------------|-------------------------|---------------------------------------------------------------|
| **Channel**  | `proper.channels`       | Base class you subclass — the "controller" for WebSockets     |
| **Cable**    | `proper.channels.cable` | Serves the WebSockets (Bearings) — protocol, multiplexing, streams, presence, recovery |
| **RedisCable** | `proper.channels.redis_cable` | `Cable` on several machines, through Redis |
| **BaseCable** | `proper.channels.base` | What `Cable` builds on: forwarding broadcasts from other processes. On its own (`CABLE = {}`) it serves no WebSockets |

Channel code is regular sync Python. Channel methods run in the cable's worker threads (`workers`, 4 by default), with database connections managed automatically. The commands of one connection run one at a time, in the order they arrived, each in a `contextvars` context of its own: what one sets on `current` doesn't reach the next.

Outbound, Bearings writes the frames: `send()` and subscription confirmations go to one connection, a `broadcast()` is one frame written to every subscriber of the stream.

The browser client (`cable.js`), the cable's configuration and backends (Bearings, RedisCable) and a full example are in [cable.md](cable.md). The frames on the wire are in [reference/cable_protocol.md](reference/cable_protocol.md).

## Table of Contents

- [Installation](#installation)
- [Defining Channels](#defining-channels)
- [Channel Lifecycle](#channel-lifecycle)
- [Action Methods](#action-methods)
- [Streams and Broadcasting](#streams-and-broadcasting)
- [Turbo Streams](#turbo-streams)
- [Channel Properties](#channel-properties)
- [Authentication](#authentication)
- [When Nothing Arrives](#when-nothing-arrives)
- [Testing](#testing)


## Installation

Install the channels addon with:

```bash
proper install channels
```

This creates the files below:

- `config/channels.py` file (sets `CABLE_PATH`, `CABLE_PORT` and the `CABLE` backend dict: `Cable`, see below)
- `channels/app_channel.py` - the `AppChannel` base your channels inherit from
- `channels/__init__.py` - imports each channel module, so its decorator runs
- Adds `cable.js` to the `assets/js` folder at the project root, registers it in the import map (as `"cable"`), and adds `import "cable"` to `application.js`
- `tests/channels/`

`proper g channel Chat` creates `channels/chat_channel.py` and adds its import to `channels/__init__.py`. A channel module that is not imported is never registered.


## Defining Channels

A channel is a subclass of `AppChannel`, registered with the router using the `@router.channel()` decorator. Channels are the WebSocket equivalent of controllers, and `AppChannel` is their `AppController`.

```python {title="myapp/channels/chat_channel.py"}
from ..router import router
from .app_channel import AppChannel


@router.channel()
class ChatChannel(AppChannel):
    def subscribed(self):
        room = self.params["room"]
        self.stream_from(f"chat_{room}")

    def unsubscribed(self):
        pass

    def speak(self, data):
        self.broadcast(f"chat_{self.params['room']}", {
            "message": data["message"],
        })
```

The channel is registered under its class name (e.g. `"ChatChannel"`), which is what clients use to subscribe. `@router.channel("chat")` registers it under another name; clients subscribe with that name, and `channel_name` (in every frame) is that name.


## Channel Lifecycle

### `subscribed()`

Called when a client subscribes to this channel. Use it to:

- Set up streams with `self.stream_from()`
- Perform authorization checks
- Send an initial message to the client

```python
def subscribed(self):
    if not self.authenticated:
        self.reject()
        return
    self.stream_from(f"notifications_{current.user.id}")
    self.send({"greeting": "welcome!"})
```

Messages sent during `subscribed()` are buffered and flushed to the client before the subscription confirmation. If the channel calls `self.reject()`, the buffered messages are discarded. The streams of `stream_from()` and the presence of `track()` in `subscribed()` start only once it returns without rejecting: a broadcast made while `subscribed()` runs doesn't reach the client, and a rejected channel never appears in a presence list.

### `unsubscribed()`

Called when the client unsubscribes, when the connection closes (tab closed, network drop noticed, server closed it via `disconnect()`, or it fell `CABLE_MAX_PENDING_BYTES` behind and was closed with code 1013), and for every open connection when the server stops cleanly. Use it for cleanup. The framework removes the channel from all streams before calling this method.

It does not run if the process is killed or crashes, and for a connection that dies silently it runs late: the cable closes a connection that answers no ping for `idle_timeout` (60 s), and `unsubscribed()` runs then. `cable.js` answers the cable's `{"c":"WSE","t":"ping"}` with a PONG, so a page that only listens isn't closed. Do not put critical cleanup solely here.

### Rejection

Call `self.reject()` inside `subscribed()` to deny the subscription. The client receives a `reject_subscription` message and the channel is not stored.

```python
def subscribed(self):
    if not self.authenticated:
        self.reject()
        return
    self.stream_from(f"user_{current.user.id}")
```


## Action Methods

A method your channel class defines (or a class between it and `Channel`, such as a mixin), other than the blocked names below, can be invoked by the client as an action. The client sends a `message` command with an `action` name and optional `data`. The method is always called as `method(data)`, with `{}` when the client sent no data, so every action takes a `data` argument.

```python
@router.channel()
class ChatChannel(AppChannel):
    def subscribed(self):
        self.stream_from(f"chat_{self.params['room']}")

    def speak(self, data):
        self.broadcast(f"chat_{self.params['room']}", {
            "message": data["message"],
            "sender": data.get("sender"),
        })

    def typing(self, data):
        self.broadcast(f"chat_{self.params['room']}", {
            "typing": True,
            "user": data["user"],
        })
```

The framework blocks the following from being called as actions:

- Methods starting with `_` (private methods)
- Empty action names
- Names that aren't a method defined by your channel class or its mixins: an attribute such as `app` or `Session`, or a method of `Channel` itself (`unknown_action`)
- Lifecycle-only methods: `subscribed`, `unsubscribed`
- Channel API methods (calling these from the client would let the client bypass server logic): `send`, `broadcast`, `reject`, `stream_from`, `stop_stream_from`, `stop_all_streams`, `track`, `untrack`, `update_presence`, `find_user`, `find_session`

Every other method your class defines is reachable from the client: prefix helpers with `_`.

One action name is conventional: `receive`. The client's `sub.send(data)` is shorthand for `perform("receive", data)`, so defining a `receive(self, data)` method makes it the default handler for messages sent that way.

### Replies

`sub.perform()` returns a promise that resolves with what the action returned (`null` if nothing). To report an error to the caller, raise `ActionError(reason, **data)` (from `proper.channels`): the promise rejects with `{reason, ...data}`. It is the action's answer, not a failure: nothing is logged. Any other exception is logged and the promise rejects with `{reason: "error"}`, without details. The promise also rejects with `{reason: "not_subscribed" | "invalid_action" | "unknown_action"}` when there is nothing to run (an action is a public method your channel class defines, or a mixin of it: not an attribute such as `app` or `Session`, nor a method of `Channel`), and `{reason: "timeout"}` after 10 seconds without a reply (`sub.perform(action, data, {timeout})` sets it, in milliseconds). A timeout doesn't cancel the action: the server may still run it, and a late reply is dropped, so a retry can run it twice. Calling `perform()` without awaiting is fine: an unawaited rejection is not reported.

```python
from proper.channels import ActionError

class ChatChannel(AppChannel):
    def speak(self, data):
        text = data.get("message", "").strip()
        if len(text) > 500:
            raise ActionError("too_long", max=500)
        message = Message.create(room_id=self.params["room"], text=text)
        self.broadcast(f"chat_{self.params['room']}", {"message": text})
        return {"id": message.id}
```

```javascript
try {
  const { id } = await chat.perform("speak", { message })
} catch (error) {
  console.log(error.reason, error.max)
}
```


## Streams and Broadcasting

Streams are named pub/sub topics. Multiple channels can subscribe to the same stream, and broadcasting to a stream delivers the message to all of them.

### Available Methods

| Method                              | Description                                              |
|--------------------------------------|----------------------------------------------------------|
| `self.stream_from(name)`            | Subscribe this channel to a named stream                 |
| `self.stop_stream_from(name)`       | Unsubscribe this channel from a stream                   |
| `self.stop_all_streams()`           | Unsubscribe this channel from all streams                |
| `self.send(data)`                   | Send data to **this connection only**                    |
| `self.broadcast(stream_name, data)` | Send data to **all subscribers** of a stream             |
| `self.track(name, data, key=)` / `self.untrack(name)` / `self.update_presence(data)` | Who is in a stream (see [Presence](#presence)) |

A broadcast doesn't go through `send()`, even an overridden one: every subscriber of a stream gets the same data. To tell different users different things, use different streams (e.g. `f"user:{user.id}:notices"`).

Who gets a broadcast is who listens to its stream, so the feature's shape is its stream names: everyone (`"announcements"`), a group (`f"chat_{room.id}"`), one user (`f"inbox_{current.user.id}"`, named after the verified user, never after `params`), something in progress (`f"import_{job.id}"`). A channel can stream from several; put a `kind` field in the data when the page must tell them apart.

### Presence

`self.track(stream, data=None, *, key=None)` lists the connection among those present in a stream (after `stream_from(stream)`; `ValueError` otherwise). Key: `key` if given, else the user's id, else a random `anon:...` per connection. Decide the key on the server, never from `params`. One key per connection (a second `track()` with another raises). The stream's subscribers get `presence_join` on a user's first connection and `presence_leave` on their last (three tabs count once); `self.untrack(stream)`, `stop_stream_from()`, unsubscribing and disconnecting all leave (a connection with several channels that track the same stream leaves when the last of them stops); `self.update_presence(data)` changes the data everywhere the connection is present (`presence_update`). `app.cable.presence(stream)` → `{key: {"data", "connections"}}`, `app.cable.presence_stats(stream)` → `{"users", "connections"}`. The confirmation carries `presence: {stream: {key: data}}` for the tracked streams. Client: the `presence(users, change)` callback (list on confirmation with `change=null`; then `change={event: "join"|"leave"|"update", userId, data}`). `Cable(presence=False)` turns it off (`track()` raises). `presence_max_data_size` (4096 bytes as JSON) and `presence_max_members` (0: no limit) bound it (`ValueError`). With `RedisCable` the list spans the machines.


### Stream Naming

Stream names are arbitrary strings. The convention is to use a descriptive prefix and a dynamic suffix:

```python
self.stream_from(f"chat_{room_id}")
self.stream_from(f"notifications_{user_id}")
self.stream_from(f"document_{doc_id}_edits")
```

### Broadcasting from Outside a Channel

Any part of the application can broadcast to a stream via `app.cable`. This is the key integration point between HTTP and WebSocket: controllers and background tasks can push real-time updates to connected clients.

From a process that doesn't serve the WebSockets (a Huey worker, a shell, the
extra `PROCESSES`), each broadcast is a request to the one that does. Wrap
several in `with app.cable.batch():` to send them in one.

```python {title="myapp/controllers/message_controller.py"}
@router.resource("messages")
class MessageController(AppController):
    def create(self):
        self.form = MessageForm(self.params)
        if self.form.is_invalid:
            return self.redo()

        message = self.form.save()
        message.save()

        # Push to all WebSocket clients watching this room
        self.app.cable.broadcast(f"chat_{message.room_id}", {
            "message": message.text,
            "sender": message.author.name,
        })

        self.response.redirect_to("Message.index")
```

From a background task:

```python {title="myapp/tasks/notifications.py"}
from ..main import app

@app.queue.task()
def notify_user(user_id, payload):
    # ... process notification ...
    app.cable.broadcast(f"notifications_{user_id}", payload)
```


## Turbo Streams

Instead of JSON, broadcast a rendered `<turbo-stream>` fragment and let Turbo apply it: `app.cable.broadcast(stream, turbo_stream.append("messages", "Message.jx", message=message))`. The page subscribes with `<turbo-stream-channel channel="ChatChannel" params='{"room_id": 42}'>` (or `streamFrom(channel, params)` from `cable`), both in `cable.js`. Authorization is unchanged: the channel derives and authorizes the stream name in `subscribed()`. After a reconnection the missed fragments are applied on arrival; when they can't be recovered the element dispatches a bubbling `turbo-stream-channel:gap` event (`streamFrom(channel, params, {onGap})`): reload the content then. The builder and the stream responses are in [turbo.md](turbo.md#turbo-streams).


## Channel Properties

Inside any channel method, the following are available:

| Property          | Description                                                |
|-------------------|------------------------------------------------------------|
| `self.app`        | The `App` instance (access DB, config, cable, etc.)        |
| `self.params`     | Dict of params the client sent when subscribing            |
| `self.channel_name` | The name it was registered under (e.g. `"ChatChannel"`) |
| `self.authenticated` | `True` when the connection has a logged-in user         |
| `self.user_id`    | The id of that user, or `None`                             |
| `self.request`    | The handshake as a request: path and `query`, `headers` (`cookie`, `authorization`, `x-forwarded-for`), `remote_ip`, signed cookies |


## Authentication

When the auth addon is installed, channels authenticate from the same signed
session cookie an HTTP request uses - no token in `params`. `AppChannel` is
wired to your app's `Session` model, so the framework resolves the session from
the cookie once, at subscription time, and exposes the logged-in user as
`current.user` (and `self.authenticated`), exactly like a controller:

```python {title="myapp/channels/inbox_channel.py"}
from proper import current

from ..router import router
from .app_channel import AppChannel


@router.channel()
class InboxChannel(AppChannel):
    def subscribed(self):
        if not self.authenticated:
            self.reject()
            return
        self.stream_from(f"inbox_{current.user.id}")
```

Under the hood this is the `Session` class attribute, which `AppChannel` sets
for you. At subscription time `_authenticate()` reads the cookie, stores the
`user_id` on the channel, and makes the resolved session available as
`current.auth_session` (only inside `subscribed()`). Before every later dispatch
the framework calls `find_user(user_id)` — defined in `AppChannel` — to refresh
`current.user` from the database; the cookie itself is not re-read. A channel
with no `Session` stays anonymous (`current.user` is `None`). The cookie name and
salt are the class attributes `auth_cookie_name` and `auth_cookie_salt` (the auth
addon's by default). For custom schemes, `self.request.get_signed_cookie(...)` is
still available.

The cookie is read once per connection: the first channel that subscribes on a
socket resolves the session, and the others reuse its `user_id` (each loads the
user with `find_user`). `current.auth_session` is set only in that first
`subscribed()`.

To close a user's open connections after revoking access (a membership
removed, a ban, a sign-out), call `app.cable.disconnect(user_id=...)`. It
works from any process; the clients reconnect and subscribe again, and the
channels that no longer authorize them reject the subscription.


### Clients without cookies

`Channel.find_session()` finds the connection's session, once per connection when its first channel subscribes; by default from the signed auth cookie. Override it in `AppChannel` to accept a token, e.g. `Authorization: Bearer <token>` from `self.request.headers` (`return Session.find_by_token(token)`, falling back to `super().find_session()`); return `None` for anonymous. `self.request` also has `query` (the handshake's query string) and `remote_ip` (honors `X-Forwarded-For` when the handshake's peer is in `TRUSTED_PROXIES`; a handshake without a peer address, which only the in-memory server's `connect()` without details gives, has no `X-Forwarded-For` and `remote_ip == ""`).


## When Nothing Arrives

A broadcast to a stream without listeners is not an error. Check: the WS connection in the browser's Network panel (status 101; its frames show `subscribe`, `confirm_subscription`/`reject_subscription`, pings and broadcasts); a reject means `reject()`, an exception in `subscribed()` (server log) or an unregistered name (module not imported in `channels/__init__.py`, or `@router.channel("name")` differs from the class name); the confirmation's `streams` must include the stream broadcast to; `app.cable.streams` lists the streams with subscribers; `app.cable.health()` says whether the process serves WebSockets; a forwarded broadcast that can't reach the web process logs a warning; `received()` gets the data after JSON (dates as strings, models must be dicts). Page-scoped subscriptions must unsubscribe when the page goes away (Turbo Drive swaps the body): use `<turbo-stream-channel>` or a Stimulus controller's `connect()`/`disconnect()`; `cable.connect()` goes in `application.js`.


## Testing

`client.websocket()` (on the `TestClient`) returns a `WebSocketTestSession` that runs the app's cable from memory (`app.cable.serve_in_memory()`): no port, no threads, each frame handled right away. With `CABLE = {}`, `connect()` raises `RuntimeError`. Tests are `async`: the app needs `pytest-asyncio` (`uv add --dev pytest-asyncio`) and `@pytest.mark.asyncio` (or `asyncio_mode = "auto"`).

```python {title="myapp/tests/channels/test_chat_channel.py"}
@pytest.mark.asyncio
async def test_speak(client):
    ws = client.websocket()
    task = await ws.connect()
    confirm = await ws.subscribe("ChatChannel", room="general")
    assert confirm["type"] == "confirm_subscription"
    await ws.send_action("ChatChannel", "speak", {"message": "hi"}, room="general")
    msg = await ws.receive()
    assert msg["type"] == "broadcast" and msg["stream"] == "chat_general"
    assert msg["data"] == {"message": "hi"}
    await ws.close()   # runs unsubscribed()
    await task
```

| Method | Description |
|--------|-------------|
| `await ws.connect()` | Opens the connection; returns a task that ends when it closes. The handshake has the client's default headers (`cookie`, `authorization`, `x-forwarded-for`) and the path of `client.websocket(path)` (`CABLE_PATH` by default; a query string is allowed) |
| `await ws.subscribe(channel, positions=None, **params)` | Sends `subscribe`, returns the **first** frame back (a `send()` from `subscribed()`, a `presence_join` of a `track()`, or a recovered broadcast comes before the confirmation). `positions={stream: [{"e", "o"}, ...]}` asks for the broadcasts since |
| `await ws.send_action(channel, action, data, **params)` | Calls an action, without asking for a reply |
| `await ws.perform(channel, action, data, **params)` | Calls an action with an `id` and returns its `reply` frame (`status` `"ok"` or `"error"`, `data`), skipping what the action sent before it |
| `await ws.unsubscribe(channel, **params)` | Sends `unsubscribe` |
| `await ws.receive(timeout=1.0)` | Next frame, parsed; `TimeoutError` if none |
| `await ws.receive_raw(timeout=1.0)` | Next raw event: `{"type": "accept"}` first, then `{"type": "text", ...}` or `{"type": "close", ...}` |
| `ws.client_send(dict)` / `ws.client_send_text(str)` | Raw frames, for protocol-error tests |
| `await ws.close()` | Disconnects |

Several sessions share the cable, and `client.app.cable.broadcast(...)` from the test reaches them. `client.sign_in(session)` before `client.websocket()` puts the auth cookie on the handshake, so the channel sees `current.user`.
