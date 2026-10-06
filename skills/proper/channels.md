---
title: Channels
description: Channels addon — WebSocket system with multiplexed channels, streams, and broadcasting
last_verified: 2026-09-25
---

# Channels

Proper Channels is an installable addon that provide a channel-based WebSocket system for real-time communication. All WebSocket traffic is multiplexed over a single endpoint (`/cable` by default). Clients subscribe to named channels, and channels can broadcast messages to all subscribers of a stream.

The system has three layers:

| Layer        | Module                  | Role                                                          |
|--------------|-------------------------|---------------------------------------------------------------|
| **Channel**  | `proper.channels`       | Base class you subclass — the "controller" for WebSockets     |
| **WseCable** | `proper.channels.wse`   | Serves the WebSockets (proper-wse, Rust) — protocol, multiplexing, streams, lifecycle |
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
- [Several Machines (RedisCable)](#several-machines-rediscable)
- [Full Example](#full-example)


## Installation

Install the channels addon with:

```bash
proper install channels
```

This creates the files below and adds `proper-wse` to the app's dependencies:

- `config/channels.py` file (sets `CABLE_PATH`, `CABLE_PORT` and the `CABLE` backend dict: `WseCable`, see below)
- `channels/app_channel.py` - the `AppChannel` base your channels inherit from
- Adds `cable.js` to the `assets/js` folder at the project root, registers it in the import map (as `"cable"`), and adds `import "cable"` to `application.js`


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

The channel is registered under its class name (e.g. `"ChatChannel"`), which is what clients use to subscribe.


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

Called when the client explicitly unsubscribes or when the WebSocket connection closes (including unexpected disconnects). Use it for cleanup. The framework automatically removes the channel from all streams before calling this method.

It is best-effort on disconnect: a clean close (a `websocket.disconnect` event) calls it, but a browser tab closing hard may not deliver that event, so do not put critical cleanup solely here.

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

Any public method on a channel (other than `subscribed` and `unsubscribed`) can be invoked by the client as an action. The client sends a `message` command with an `action` name and optional `data`.

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
- Channel API methods (calling these from the client would let the client bypass server logic): `send`, `broadcast`, `reject`, `stream_from`, `stop_stream_from`, `stop_all_streams`

One action name is conventional: `receive`. The client's `sub.send(data)` is shorthand for `perform("receive", data)`, so defining a `receive(self, data)` method makes it the default handler for messages sent that way.


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


## Channel Properties

Inside any channel method, the following are available:

| Property          | Description                                                |
|-------------------|------------------------------------------------------------|
| `self.app`        | The `App` instance (access DB, config, cable, etc.)        |
| `self.params`     | Dict of params the client sent when subscribing            |
| `self.channel_name` | The class name (e.g. `"ChatChannel"`)                   |
| `self.authenticated` | `True` when the connection has a logged-in user         |
| `self.request`    | The connection request, for reading headers and signed cookies |


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
with no `Session` stays anonymous (`current.user` is `None`). For custom schemes,
`self.request.get_signed_cookie(...)` is still available.

The cookie is read once per connection: the first channel that subscribes on a
socket resolves the session, and the others reuse its `user_id` (each loads the
user with `find_user`). `current.auth_session` is set only in that first
`subscribed()`.

To close a user's open connections after revoking access (a membership
removed, a ban, a sign-out), call `app.cable.disconnect(user_id=...)`. It
works from any process; the clients reconnect and subscribe again, and the
channels that no longer authorize them reject the subscription.


## Client-Side Usage

The generated app includes `cable.js`, an ES module that handles the WebSocket protocol, subscription management, and automatic reconnection.

### Basic Usage

```javascript
import { cable } from "cable"

// Connect to the WebSocket endpoint
cable.connect()

// Subscribe to a channel
const chat = cable.subscribe("ChatChannel", { room: "general" }, {
  connected()    { console.log("subscribed") },
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

Opens the WebSocket connection. If no URL is provided, it auto-detects from the current page:

```
ws://localhost:2300/cable   (http)
wss://example.com/cable     (https)
```

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
| `sub.perform(action, data)` | Invoke a channel action with optional data  |
| `sub.send(data)`            | Shorthand for `perform("receive", data)`    |
| `sub.unsubscribe()`         | Unsubscribe and trigger `disconnected`      |

### Automatic Reconnection

On disconnect, `cable.js` reconnects with exponential backoff (1s, 2s, 4s, ... up to 30s, with jitter), for as long as the page is open. On reconnect, all existing subscriptions are automatically re-subscribed. The server pings every `CABLE_PING_INTERVAL` seconds; a connection silent for 10 seconds is taken for dead and replaced. `cable.connect()` opens one socket for the page: calling it again while connected or connecting does nothing. Call `cable.disconnect()` to stop reconnection.

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

Clients connect via WebSocket to `/cable` and exchange JSON messages. This section documents the protocol for reference; `cable.js` handles it automatically.

### Client-to-Server Commands

**Subscribe:**

```json
{"command": "subscribe", "channel": "ChatChannel", "params": {"room": "general"}}
```

**Send a message (invoke an action):**

```json
{"command": "message", "channel": "ChatChannel", "params": {"room": "general"}, "action": "speak", "data": {"message": "hello"}}
```

**Unsubscribe:**

```json
{"command": "unsubscribe", "channel": "ChatChannel", "params": {"room": "general"}}
```

### Server-to-Client Messages

**Subscription confirmed** (with the streams of the subscription):

```json
{"type": "confirm_subscription", "channel": "ChatChannel", "params": {"room": "general"}, "streams": ["chat:general"]}
```

**Subscription rejected:**

```json
{"type": "reject_subscription", "channel": "ChatChannel", "params": {"room": "general"}}
```

A reject for an unregistered channel carries `"reason": "unknown_channel"`; a reject from your own `reject()` in `subscribed()` has no `reason`.

**Data message (from `send()`):**

```json
{"type": "message", "channel": "ChatChannel", "params": {"room": "general"}, "data": {"message": "hello"}}
```

**Broadcast (from `broadcast()`).** One frame for every subscriber, so it names the stream instead of the channel and params; clients route it to every subscription streaming from it (`confirm_subscription` lists the streams). Ignore the `c` field (wse's category):

```json
{"c": "P", "type": "broadcast", "stream": "chat:general", "data": {"message": "hello"}}
```

**Error:**

```json
{"type": "error", "reason": "not_subscribed"}
```

Error reasons: `invalid_json`, `unknown_command`, `not_subscribed`, `invalid_action`, `unknown_action`, `invalid_message` (JSON that is not an object).

**Ping**, every `CABLE_PING_INTERVAL` seconds (`message` is the server's time):

```json
{"type": "ping", "message": 1791230000}
```

A handshake from another site's page is refused with a 403 (see `CABLE_ALLOWED_ORIGINS`).


## Configuration

| Setting      | Default    | Description                        |
|--------------|------------|------------------------------------|
| `CABLE_PATH` | `"/cable"` | WebSocket endpoint path            |
| `CABLE_PORT` | `0`        | Port where `WseCable` serves the WebSockets, from the web process `proper run` starts. The channels addon sets it to `PORT + 1`. Set with an empty `CABLE`, it is a `ConfigError` |
| `CABLE_ALLOWED_ORIGINS` | `[]` | Browser origins allowed besides the app's own (`HOST`, or the `Host` of the handshake; in `DEBUG`, any port of that host name). Handshakes without `Origin` (not browsers) are always allowed |
| `CABLE_PING_INTERVAL` | `3` | Seconds between the server's pings on every connection; `0` sends none |
| `CABLE_MAX_PENDING_BYTES` | `4194304` | A client with more than this many bytes waiting and nothing through in `CABLE_STALL_TIMEOUT` seconds is closed (no close handshake), and so is one with ten times as many; `0` is no limit |
| `CABLE_STALL_TIMEOUT` | `10` | See `CABLE_MAX_PENDING_BYTES` |

Set in your app config:

```python {title="myapp/config/main.py"}
CABLE_PATH = "/ws"
```


## WseCable (proper-wse)

The default backend, the one the channels addon writes. `CABLE = {"type": "proper.channels.wse.WseCable"}` serves the WebSockets with `proper-wse` (our fork of wse-server, Rust; imports as `wse_server`) on `CABLE_PORT`, inside the web process; install with `uv add "proper[wse]"` (wheels for free-threaded Python included). Channels don't change. A `broadcast()` is one frame that wse writes to every subscriber without Python, using the stream-named frames above.

- `proper run` starts it (`app.cable.start_server()`) in its web process and stops it with the server. The web server (Granian, WSGI) has no WebSockets. In production the reverse proxy routes `CABLE_PATH` to `CABLE_PORT` (the blueprint's nginx config has the block); in `DEBUG` the page announces the port in a `<meta name="cable-port">` tag, rendered by `render_importmap()`, and `cable.js` connects to it directly.
- Other processes (`PROCESSES` copies, Huey workers, shells) forward `broadcast()` and `disconnect()` to it, signed, as a `POST` to `CABLE_PATH` on `127.0.0.1:forward_port` (`CABLE_PORT + 1` by default). `app.cable.batch()` works.
- Options: `port`, `host` (`0.0.0.0`), `forward_port`, `workers` (4 threads for channel code), `max_connections` (100000), `max_outbound_queue_bytes` (64 MB: broadcasts are dropped for a connection that falls this far behind; frames are shared, so a backlog costs memory once), `backpressure_bytes` (128 KB: `broadcast()` waits while its stream's subscribers average more than this queued, so publishers slow to the pace of delivery; `0` never waits) and `backpressure_timeout` (1.0 s at most); anything else goes to `RustWSEServer` (e.g. `max_pending_handshakes`).
- Clients that stop reading are closed per `CABLE_MAX_PENDING_BYTES` and `CABLE_STALL_TIMEOUT`; `cable.js` reconnects. The original `wse-server`, or a proper-wse older than 2.6.0, is refused at startup.


## Without Channels (`CABLE = {}`)

The default for an app without the addon: a base `Cable` that serves no WebSockets. A `broadcast()` reaches no one (logged at debug level), and `client.websocket()` raises `RuntimeError` on `connect()`. Setting `CABLE_PORT` with an empty `CABLE` is a `ConfigError` at app setup.


## Several Machines (RedisCable)

`RedisCable` is `WseCable` on several machines, with Redis carrying broadcasts between them. Code doesn't change, only the config:

```python {title="myapp/config/channels.py"}
CABLE = {
    "type": "proper.channels.RedisCable",
    "url": os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    "prefix": "myapp:cable:",   # unique per app sharing a Redis
}
```

- Each machine's web process serves its own WebSockets (proper-wse). A `broadcast()` goes straight to the local subscribers of the process that makes it and to Redis; the other machines' web processes deliver it to theirs and skip their own messages.
- Processes without WebSockets (Huey workers, shells) publish to Redis directly: no HTTP forwarding, no `CABLE_PORT + 1`. `disconnect()` reaches every machine too.
- Options: `url` (`redis://localhost:6379/0`), `prefix` (`proper:cable:`), plus every `WseCable` option. Needs the `redis` package (`uv add redis`); raises if it's missing.
- Subscribes when `proper run` starts the server (waits up to 1 s), reconnects with backoff (up to 30 s). A broadcast that can't reach Redis is lost with a warning; local clients still get it. Backpressure only sees the publishing machine.
- `client.websocket()` tests run from memory, without Redis.
- Redis pub/sub carries events, not state: a presence roster or "last value" replay is up to you.


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
