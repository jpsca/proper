---
title: Channels
description: Channels addon — WebSocket system with multiplexed channels, streams, and broadcasting
last_verified: 2026-10-06
---

# Channels

Proper Channels is an installable addon that provides a channel-based WebSocket system for real-time communication. All WebSocket traffic of a page is multiplexed over one connection, served on `CABLE_PORT` (behind the proxy, at `CABLE_PATH`, `/cable` by default). Clients subscribe to named channels, and channels can broadcast messages to all subscribers of a stream.

The system has three layers:

| Layer        | Module                  | Role                                                          |
|--------------|-------------------------|---------------------------------------------------------------|
| **Channel**  | `proper.channels`       | Base class you subclass — the "controller" for WebSockets     |
| **Cable** | `proper.channels.cable`   | Serves the WebSockets (proper-wse, Rust) — protocol, multiplexing, streams, lifecycle |
| **Cable**    | `proper.channels`       | Base of the cables: forwarding from other processes. On its own (`CABLE = {}`) it serves no WebSockets |

Channel code is regular sync Python. Channel methods run in the cable's worker threads (`workers`, 4 by default), with database connections managed automatically. The commands of one connection run one at a time, in the order they arrived, each in a `contextvars` context of its own: what one sets on `current` doesn't reach the next.

Outbound, wse writes the frames: `send()` and subscription confirmations go to one connection, a `broadcast()` is one frame written to every subscriber of the stream.

## Table of Contents

- [Installation](#installation)
- [Defining Channels](#defining-channels)
- [Channel Lifecycle](#channel-lifecycle)
- [Action Methods](#action-methods)
- [Streams and Broadcasting](#streams-and-broadcasting)
- [Turbo Streams](#turbo-streams)
- [Channel Properties](#channel-properties)
- [Client-Side Usage](#client-side-usage)
- [Wire Protocol](#wire-protocol)
- [Configuration](#configuration)
- [Testing](#testing)
- [Full Example](#full-example)


## Installation

Install the channels addon with:

```bash
proper install channels
```

This creates the files below and adds `proper-wse` to the app's dependencies:

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

Messages sent during `subscribed()` are buffered and flushed to the client before the subscription confirmation. If the channel calls `self.reject()`, the buffered messages are discarded.

### `unsubscribed()`

Called when the client unsubscribes, when the connection closes (tab closed, network drop noticed, server closed it via `disconnect()` or the slow-client watcher), and for every open connection when the server stops cleanly. Use it for cleanup. The framework removes the channel from all streams before calling this method.

It does not run if the process is killed or crashes, and for a connection that dies silently it runs late: wse closes a connection that sends it nothing for `idle_timeout` (60 s, checked every `ping_interval`, 25 s), and `unsubscribed()` runs then. `cable.js` answers wse's own `{"c":"WSE","t":"ping"}` with a PONG, so a page that only listens isn't closed. Needs proper-wse >= 2.6.2: older versions deadlocked on that close. Do not put critical cleanup solely here.

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

Any public method on a channel (other than the blocked names below) can be invoked by the client as an action. The client sends a `message` command with an `action` name and optional `data`. The method is always called as `method(data)`, with `{}` when the client sent no data, so every action takes a `data` argument.

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
- Methods that don't exist or aren't callable
- Lifecycle-only methods: `subscribed`, `unsubscribed`
- Channel API methods (calling these from the client would let the client bypass server logic): `send`, `broadcast`, `reject`, `stream_from`, `stop_stream_from`, `stop_all_streams`, `find_user`

Every other public method is reachable from the client: prefix helpers with `_`.

One action name is conventional: `receive`. The client's `sub.send(data)` is shorthand for `perform("receive", data)`, so defining a `receive(self, data)` method makes it the default handler for messages sent that way.

### Presence

`self.track(stream, data=None, *, key=None)` lists the connection among those present in a stream (after `stream_from(stream)`; `ValueError` otherwise). Key: `key` if given, else the user's id, else a random `anon:...` per connection. Decide the key on the server, never from `params`. One key per connection (a second `track()` with another raises). The stream's subscribers get `presence_join` on a user's first connection and `presence_leave` on their last (three tabs count once); `self.untrack(stream)`, `stop_stream_from()`, unsubscribing and disconnecting all leave; `self.update_presence(data)` changes the data everywhere the connection is present (`presence_update`). `app.cable.presence(stream)` → `{key: {"data", "connections"}}`, `app.cable.presence_stats(stream)` → `{"users", "connections"}`. The confirmation carries `presence: {stream: {key: data}}` for the tracked streams. Client: the `presence(users, change)` callback (list on confirmation with `change=null`; then `change={event: "join"|"leave"|"update", userId, data}`). `Cable(presence=False)` turns it off (`track()` raises); wse's `presence_max_data_size`, `presence_max_members` bound it. One machine only.

### Replies

`sub.perform()` returns a promise that resolves with what the action returned (`null` if nothing). To report an error to the caller, raise `ActionError(reason, **data)` (from `proper.channels`): the promise rejects with `{reason, ...data}`. It is the action's answer, not a failure: nothing is logged. Any other exception is logged and the promise rejects with `{reason: "error"}`, without details. The promise also rejects with `{reason: "not_subscribed" | "invalid_action" | "unknown_action"}` when there is nothing to run, and `{reason: "timeout"}` after 10 seconds without a reply (`sub.perform(action, data, {timeout})` sets it, in milliseconds). A timeout doesn't cancel the action: the server may still run it, and a late reply is dropped, so a retry can run it twice. Calling `perform()` without awaiting is fine: an unawaited rejection is not reported.

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

A broadcast doesn't go through `send()`, even an overridden one: every subscriber of a stream gets the same data. To tell different users different things, use different streams (e.g. `f"user:{user.id}:notices"`).

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

Proper bundles Turbo. Instead of broadcasting JSON and rebuilding the DOM in `received()`, broadcast a rendered Jx component wrapped in a `<turbo-stream>` and let Turbo apply it.

Build the fragment with the `turbo_stream` builder (`proper.turbo`, re-exported as `proper.turbo_stream`). Call an action method — `append`, `prepend`, `replace`, `update`, `remove`, `before`, `after`, `morph`, `refresh` — with a target id (or a model, via `dom_id`) and a `component` relpath plus props (or ready-made `html`/`content`):

```python
from proper import turbo_stream

app.cable.broadcast(
    f"chat_{room_id}",
    turbo_stream.append("messages", "Message.jx", message=message),
)
```

The channels addon ships the bridge inside `cable.js` (imported from `application.js` on install), which defines:

- `<turbo-stream-channel channel="ChatChannel" params='{"room_id": 42}'>` — declarative subscription that feeds each frame to `Turbo.renderStreamMessage`.
- `streamFrom(channel, params)` — the imperative equivalent (`import { streamFrom } from "cable"`).

Authorization is unchanged: the client sends `params`, and the channel derives and authorizes the stream name in `subscribed()`. The same fragment also serves an HTTP response — return it from a controller with `render(stream=...)`, or render a `*.turbo_stream.jx` view. The builder, frames, and stream responses are documented in full in [turbo.md](turbo.md).


After a reconnection the missed `<turbo-stream>` fragments are applied on arrival. When they can't be recovered, `<turbo-stream-channel>` dispatches a bubbling `turbo-stream-channel:gap` DOM event (`streamFrom(channel, params, {onGap})` takes a function): listen to it to reload the content, e.g. `Turbo.visit(location.href, {action: "replace"})`.

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

`Channel.find_session()` finds the connection's session, once per connection when its first channel subscribes; by default from the signed auth cookie. Override it in `AppChannel` to accept a token, e.g. `Authorization: Bearer <token>` from `self.request.headers` (`return Session.find_by_token(token)`, falling back to `super().find_session()`); return `None` for anonymous. `self.request` also has `query` (the handshake's query string) and `remote_ip` (honors `X-Forwarded-For`).

## Client-Side Usage

The generated app includes `cable.js`, an ES module that handles the WebSocket protocol, subscription management, and automatic reconnection.

### Basic Usage

```javascript
import { cable } from "cable"

// Connect to the WebSocket endpoint
cable.connect()

// Subscribe to a channel
const chat = cable.subscribe("ChatChannel", { room: "general" }, {
  connected({ reconnected, recovered }) { if (reconnected && recovered === false) reload() },
  presence(users, change) { renderWhoIsHere(users) },
  disconnected() { console.log("disconnected") },
  rejected()     { console.log("subscription denied") },
  received(data) { console.log("got:", data) },
})

// Invoke an action on the channel
chat.perform("speak", { message: "hello" })

// Shorthand for perform("receive", data)
chat.send({ message: "hello" })

// Unsubscribe from the channel
chat.unsubscribe()

// Disconnect entirely
cable.disconnect()
```

### `cable.connect(url?)`

Opens the WebSocket connection. If no URL is provided, it connects to `/cable` on the current host (`ws:` on http, `wss:` on https). When the page has a `<meta name="cable-port">` tag (`render_importmap()` adds it in `DEBUG`), it uses that port on the same host name instead:

```
ws://localhost:2301/cable   (development, CABLE_PORT from the meta tag)
wss://example.com/cable     (production, behind the proxy)
```

The path is hardcoded: with another `CABLE_PATH`, pass the full URL.

### `cable.subscribe(channel, params?, callbacks?)`

Creates a subscription. The `params` argument is optional — if the second argument has callback keys (`connected`, `disconnected`, `received`, `rejected`), it is treated as callbacks with empty params:

```javascript
// With params and callbacks
cable.subscribe("ChatChannel", { room: "general" }, { received(data) { ... } })

// Callbacks only (no params)
cable.subscribe("ChatChannel", { received(data) { ... } })
```

Returns a `Subscription` object.

### Subscription Methods

| Method                      | Description                                 |
|-----------------------------|---------------------------------------------|
| `sub.perform(action, data, {timeout}?)` | Invoke a channel action; a promise with its reply (see [Replies](#replies)) |
| `sub.send(data, {timeout}?)` | Shorthand for `perform("receive", data)`    |
| `sub.unsubscribe()`         | Unsubscribe and trigger `disconnected`      |

### Automatic Reconnection

On disconnect, `cable.js` reconnects with exponential backoff (1s, 2s, 4s, ... up to 30s, with jitter), for as long as the page is open. On reconnect, all existing subscriptions are automatically re-subscribed, and the `perform()` calls made while disconnected are sent after them (at most 100 wait; past that the oldest rejects with `{reason: "offline"}`; their timeouts keep running).

### Recovery

The server keeps the last broadcasts of each stream (`recovery=True` in `Cable`, the default; wse's `recovery_buffer_size` 128 per stream, `recovery_ttl` 300 s, `recovery_memory_budget` 256 MB). Each broadcast carries a stamp (`tp` stream, `e` epoch, `o` offset); `cable.js` tracks the position per stream, sends it with each `subscribe`, drops duplicates, and when it sees a hole (wse dropped frames for a slow connection) holds the later frames and subscribes again to fetch the missed ones. The missed broadcasts come through `received()` in order. `connected(info)` gets `{reconnected, recovered}`: `recovered` is `true` when all missed ones were sent, `false` when they couldn't be (server restarted, more than the buffer holds, stream without history) — reload the state then — and `null` when nothing was asked (first subscription, or a stream with no broadcasts before the drop; what it broadcast meanwhile is lost). `send()` messages are not recovered, only broadcasts. The server pings every `CABLE_PING_INTERVAL` seconds; a connection silent for three intervals (at least 10 s) is taken for dead and replaced. `cable.connect()` opens one socket for the page: calling it again while connected or connecting does nothing. Call `cable.disconnect()` to stop reconnection.

### Multiple Subscriptions

A single WebSocket connection can hold multiple subscriptions — to different channels or to the same channel with different params:

```javascript
const general = cable.subscribe("ChatChannel", { room: "general" }, { ... })
const random  = cable.subscribe("ChatChannel", { room: "random" }, { ... })
const notifications = cable.subscribe("NotificationChannel", { ... })
```

Each subscription is identified by its channel name + params combination.

### Loading cable.js

The installer registers `cable.js` in the import map (as `"cable"`) and adds
`import "cable"` to `application.js`, so it loads with your app bundle — no
manual `<script>` tag needed. Import it directly:

```javascript
import { cable } from "cable"
```


## Wire Protocol

Clients connect via WebSocket (see `cable.connect()`) and exchange JSON messages. This section documents the protocol for reference; `cable.js` handles it automatically.

### Client-to-Server Commands

**Subscribe.** `positions` is optional: the last stamp seen per stream; the server sends again the broadcasts after it, for the streams the channel streams from (they may arrive before the confirmation). Sending it for an existing subscription also recovers:

```json
{"command": "subscribe", "channel": "ChatChannel", "params": {"room": "general"}, "positions": {"chat_general": {"e": "0000abcd", "o": 41}}}
```

**Send a message (invoke an action).** `id` is optional; with one, the server answers with a `reply`:

```json
{"command": "message", "channel": "ChatChannel", "params": {"room": "general"}, "action": "speak", "data": {"message": "hello"}, "id": 7}
```

**Unsubscribe:**

```json
{"command": "unsubscribe", "channel": "ChatChannel", "params": {"room": "general"}}
```

### Server-to-Client Messages

**Subscription confirmed** (with the streams of the subscription; subscribing again to an existing subscription only re-sends this):

```json
{"type": "confirm_subscription", "channel": "ChatChannel", "params": {"room": "general"}, "streams": ["chat_general"], "positions": {"chat_general": {"e": "0000abcd", "o": 42}}, "recovered": true, "presence": {}}
```

`presence` is `{stream: {key: data}}` for the streams the channel tracks. Presence changes arrive as wse frames to every subscriber of the stream, possibly before the confirmation of the subscription that caused them: `{"c": "WSE", "t": "presence_join" | "presence_leave" | "presence_update", "p": {"topic", "user_id", "data"}}`.

`positions` is where each stream is now (`null` for one with no broadcasts yet); `recovered` is `true` when every missed broadcast asked for was sent again, `false` when some couldn't be, `null` when none were asked (always `null` with `recovery=False`).

**Subscription rejected:**

```json
{"type": "reject_subscription", "channel": "ChatChannel", "params": {"room": "general"}}
```

A reject for an unregistered channel carries `"reason": "unknown_channel"`; one for a `subscribed()` that raised an exception (logged, its streams stopped) carries `"reason": "error"`; a reject from your own `reject()` in `subscribed()` has no `reason`.

**Data message (from `send()`):**

```json
{"type": "message", "channel": "ChatChannel", "params": {"room": "general"}, "data": {"message": "hello"}}
```

**Broadcast (from `broadcast()`).** One frame for every subscriber, so it names the stream instead of the channel and params; clients route it to every subscription streaming from it (`confirm_subscription` lists the streams). Ignore the `c` field (wse's category). `tp`/`e`/`o` are the recovery stamp (stream, epoch of its buffer, offset); absent with `recovery=False`:

```json
{"tp": "chat_general", "e": "0000abcd", "o": 42, "c": "P", "type": "broadcast", "stream": "chat_general", "data": {"message": "hello"}}
```

**Reply** to a `message` with an `id`: `status: "ok"` with what the action returned as `data` (`null` if nothing), or `status: "error"` with a `reason` in `data` (an `ActionError`'s reason and other data; `error` for any other exception; `not_subscribed`, `invalid_action` or `unknown_action` when there was nothing to run):

```json
{"type": "reply", "id": 7, "channel": "ChatChannel", "params": {"room": "general"}, "status": "ok", "data": {"id": 42}}
{"type": "reply", "id": 7, "channel": "ChatChannel", "params": {"room": "general"}, "status": "error", "data": {"reason": "too_long", "max": 500}}
```

**Error**, for a `message` without an `id` that couldn't run (its reason and an `ActionError`'s data at the top level; any other exception in the action sends nothing), and for a command the server couldn't read:

```json
{"type": "error", "reason": "not_subscribed"}
```

Error reasons: `invalid_json`, `unknown_command`, `invalid_message` (JSON that is not an object), `not_subscribed`, `invalid_action`, `unknown_action`, and an `ActionError`'s reason.

**Ping**, wse's own, every `CABLE_PING_INTERVAL` seconds. The client answers `{"c":"WSE","t":"PONG","p":{}}`; one that answers none for the cable's `idle_timeout` (60 s) is closed:

```json
{"c": "WSE", "t": "ping", "p": {"server_time": "2026-10-06T12:00:00.000Z"}}
```

A handshake from another site's page is refused with a 403 (see `CABLE_ALLOWED_ORIGINS`).


## Configuration

| Setting      | Default    | Description                        |
|--------------|------------|------------------------------------|
| `CABLE_PATH` | `"/cable"` | Path the proxy routes to `CABLE_PORT`, and where other processes `POST` forwarded broadcasts. `cable.js` hardcodes `/cable` |
| `CABLE_PORT` | `0`        | Port where `Cable` serves the WebSockets, from the web process `proper run` starts. The channels addon sets it to `PORT + 1`. Set with an empty `CABLE`, it is a `ConfigError` |
| `CABLE_ALLOWED_ORIGINS` | `[]` | Browser origins allowed besides the handshake's own `Host`, the app's `HOST` (http and https) and, in `DEBUG`, `localhost`/`127.0.0.1` on `PORT` (`allowed_origins()`, passed to wse). Handshakes without `Origin` (not browsers) are always allowed; others get a 403 |
| `CABLE_PING_INTERVAL` | `3` | Seconds between wse's pings on every connection: an integer, at least 1, less than `CABLE['idle_timeout']` (60) |
| `CABLE_MAX_PENDING_BYTES` | `4194304` | A client with more than this many bytes waiting and nothing through in `CABLE_STALL_TIMEOUT` seconds is closed (no close handshake), and so is one with ten times as many; `0` is no limit |
| `CABLE_STALL_TIMEOUT` | `10` | See `CABLE_MAX_PENDING_BYTES` |

They go in `config/channels.py` (imported from `config/__init__.py`). Changing `CABLE_PATH` also means changing the proxy location and passing the URL to `cable.connect()`. With a `CABLE` set, they are validated at startup (`ConfigError`): `CABLE_PORT` 0–65535, `CABLE_PATH` starting with `/`, the ping interval and `idle_timeout` as above, `CABLE_MAX_PENDING_BYTES` ≥ 0, `CABLE_STALL_TIMEOUT` > 0; and `CABLE` may not set `ping_interval`, `allowed_origins` or `recovery_enabled`, which the settings and `recovery` decide.


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
| `await ws.subscribe(channel, positions=None, **params)` | Sends `subscribe`, returns the **first** frame back (a `send()` from `subscribed()`, or a recovered broadcast, comes before the confirmation). `positions={stream: {"e", "o"}}` asks for the broadcasts since |
| `await ws.send_action(channel, action, data, **params)` | Calls an action, without asking for a reply |
| `await ws.perform(channel, action, data, **params)` | Calls an action with an `id` and returns its `reply` frame (`status` `"ok"` or `"error"`, `data`), skipping what the action sent before it |
| `await ws.unsubscribe(channel, **params)` | Sends `unsubscribe` |
| `await ws.receive(timeout=1.0)` | Next frame, parsed; `TimeoutError` if none |
| `await ws.receive_raw(timeout=1.0)` | Next raw event: `{"type": "accept"}` first, then `{"type": "text", ...}` or `{"type": "close", ...}` |
| `ws.client_send(dict)` / `ws.client_send_text(str)` | Raw frames, for protocol-error tests |
| `await ws.close()` | Disconnects |

Several sessions share the cable, and `client.app.cable.broadcast(...)` from the test reaches them. `client.sign_in(session)` before `client.websocket()` puts the auth cookie on the handshake, so the channel sees `current.user`.


## Cable (proper-wse)

The default backend, the one the channels addon writes. `CABLE = {"type": "proper.channels.Cable"}` serves the WebSockets with `proper-wse` (our fork of wse-server, Rust; imports as `wse_server`) on `CABLE_PORT`, inside the web process; `proper install channels` adds it to the app's dependencies, or `uv add proper-wse` (wheels for free-threaded Python included). Channels don't change. A `broadcast()` is one frame that wse writes to every subscriber without Python, using the stream-named frames above.

- `proper run` starts it (`app.cable.start_server()`) in its web process and stops it with the server. The web server (Granian, WSGI) has no WebSockets. In production the reverse proxy routes `CABLE_PATH` to `CABLE_PORT` (the blueprint's nginx config has the block); in `DEBUG` the page announces the port in a `<meta name="cable-port">` tag, rendered by `render_importmap()`, and `cable.js` connects to it directly.
- Other processes (`PROCESSES` copies, Huey workers, shells) forward `broadcast()` and `disconnect()` to it, signed, as a `POST` to `CABLE_PATH` on `127.0.0.1:forward_port` (`CABLE_PORT + 1` by default). `app.cable.batch()` works.
- Options: `port`, `host` (`0.0.0.0`), `forward_port`, `workers` (4 threads for channel code), `max_connections` (100000), `max_outbound_queue_bytes` (64 MB: broadcasts are dropped for a connection that falls this far behind; frames are shared, so a backlog costs memory once), `backpressure_bytes` (128 KB: `broadcast()` waits while its stream's subscribers average more than this queued, so publishers slow to the pace of delivery; `0` never waits) and `backpressure_timeout` (1.0 s at most), `recovery` (True: keep the last broadcasts of each stream for reconnecting clients), `presence` (True: who is in each stream, for `track()`); anything else goes to `RustWSEServer` (e.g. `max_pending_handshakes`, `recovery_buffer_size`, `recovery_ttl`, `recovery_memory_budget`, `presence_max_data_size`, `presence_max_members`).
- Clients that stop reading are closed per `CABLE_MAX_PENDING_BYTES` and `CABLE_STALL_TIMEOUT`; `cable.js` reconnects. The original `wse-server`, or a proper-wse older than 2.6.0, is refused at startup; the channels addon requires >= 2.6.2.


## Without Channels (`CABLE = {}`)

The default for an app without the addon: a base `Cable` that serves no WebSockets. A `broadcast()` reaches no one (logged at debug level), and `client.websocket()` raises `RuntimeError` on `connect()`. Setting `CABLE_PORT` with an empty `CABLE` is a `ConfigError` at app setup.


## Full Example

A complete chat feature with a channel, a controller that broadcasts on message creation, and the client-side code.

**Channel:**

```python {title="myapp/channels/chat_channel.py"}
from ..router import router
from .app_channel import AppChannel


@router.channel()
class ChatChannel(AppChannel):
    def subscribed(self):
        self.stream_from(f"chat_{self.params['room']}")

    def speak(self, data):
        self.broadcast(f"chat_{self.params['room']}", {
            "message": data["message"],
        })
```

**Controller (creates a persisted message and broadcasts):**

```python {title="myapp/controllers/message_controller.py"}
from ..models import Message
from ..router import router
from .app_controller import AppController


@router.resource("rooms/:room_id/messages")
class MessageController(AppController):
    def create(self):
        room_id = self.params["room_id"]
        message = Message.create(
            room_id=room_id,
            text=self.params["text"],
        )
        self.app.cable.broadcast(f"chat_{room_id}", {
            "message": message.text,
            "id": message.id,
        })
        self.response.redirect_to("Message.index", room_id=room_id)
```

**Client:**

```javascript
import { cable } from "cable"

cable.connect()

const chat = cable.subscribe("ChatChannel", { room: "general" }, {
  received(data) {
    const el = document.createElement("div")
    el.textContent = data.message
    document.getElementById("messages").appendChild(el)
  },
})

document.getElementById("send-btn").addEventListener("click", () => {
  const input = document.getElementById("message-input")
  chat.perform("speak", { message: input.value })
  input.value = ""
})
```
