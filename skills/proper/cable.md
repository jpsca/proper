---
title: The Cable
description: Channels addon, transport side: the cable.js browser client (connect, subscribe, perform, reconnection, recovery), CABLE_* settings, the Bearings cable and its options, RedisCable for several machines, a full chat example
last_verified: 2026-10-31
sources:
  - src/proper/channels
  - src/proper/tools/cable.py
  - src/proper/_blueprints/addon_channels
---

# The Cable

The cable is what carries the channels: the WebSocket server inside the web process and the `cable.js` client. Writing channels is in [channels.md](channels.md); the JSON frames are in [reference/cable_protocol.md](reference/cable_protocol.md).

## Table of Contents

- [Client-Side Usage](#client-side-usage)
- [Configuration](#configuration)
- [Cable (Bearings)](#cable-bearings)
- [Without Channels (`CABLE = {}`)](#without-channels-cable--)
- [Several Machines (RedisCable)](#several-machines-rediscable)
- [Full Example](#full-example)


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

Creates a subscription. The `params` argument is optional — if the second argument has callback keys (`connected`, `disconnected`, `received`, `rejected`, `presence`), it is treated as callbacks with empty params:

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
| `sub.perform(action, data, {timeout}?)` | Invoke a channel action; a promise with its reply (see [Replies](channels.md#replies)) |
| `sub.send(data, {timeout}?)` | Shorthand for `perform("receive", data)`    |
| `sub.unsubscribe()`         | Unsubscribe and trigger `disconnected`      |

### Automatic Reconnection

On disconnect, `cable.js` reconnects with exponential backoff (1s, 2s, 4s, ... up to 30s, with jitter), for as long as the page is open. On reconnect, all existing subscriptions are automatically re-subscribed, and the `perform()` calls made while disconnected are sent after them (at most 100 wait; past that the oldest rejects with `{reason: "offline"}`; their timeouts keep running).

### Recovery

The server keeps the last broadcasts of each stream (`recovery=True` in `Cable`, the default; `recovery_buffer_size` 128 per stream, `recovery_ttl` 300 s, `recovery_memory_budget` 256 MB). Each broadcast carries a stamp (`tp` stream, `e` epoch, `o` offset); `cable.js` tracks the position per stream, sends it with each `subscribe`, drops duplicates, and when it sees a hole holds the later frames and subscribes again to fetch the missed ones. The missed broadcasts come through `received()` in order. `connected(info)` gets `{reconnected, recovered}`: `recovered` is `true` when all missed ones were sent, `false` when they couldn't be (server restarted, more than the buffer holds, stream without history) — reload the state then — and `null` when nothing was asked (first subscription, or a stream with no broadcasts before the drop; what it broadcast meanwhile is lost). `send()` messages are not recovered, only broadcasts. The server pings every `CABLE_PING_INTERVAL` seconds; a connection silent for three intervals (at least 10 s) is taken for dead and replaced. `cable.connect()` opens one socket for the page: calling it again while connected or connecting does nothing. Call `cable.disconnect()` to stop reconnection.

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


## Configuration

| Setting      | Default    | Description                        |
|--------------|------------|------------------------------------|
| `CABLE_PATH` | `"/cable"` | Path the proxy routes to `CABLE_PORT`, and where other processes `POST` forwarded broadcasts. `cable.js` hardcodes `/cable` |
| `CABLE_PORT` | `0`        | Port where `Cable` serves the WebSockets, from the web process `proper run` starts. The channels addon sets it to `PORT + 1`. Set with an empty `CABLE`, it is a `ConfigError` |
| `CABLE_ALLOWED_ORIGINS` | `[]` | Browser origins allowed besides the handshake's own `Host`, the app's `HOST` (http and https) and, in `DEBUG`, `localhost`/`127.0.0.1` on `PORT` and any port of the handshake's host name (`allowed_origins()` plus Bearings' `any_port_origin`, checked at the handshake). Handshakes without `Origin` (not browsers) are always allowed; others get a 403 |
| `CABLE_PING_INTERVAL` | `3` | Seconds between the cable's pings on every connection: an integer, at least 1, less than `CABLE['idle_timeout']` (60) |
| `CABLE_MAX_PENDING_BYTES` | `4194304` | A client this many bytes behind is closed; `cable.js` reconnects and recovers. At least 1 |

They go in `config/channels.py` (imported from `config/__init__.py`). Changing `CABLE_PATH` also means changing the proxy location and passing the URL to `cable.connect()`. With a `CABLE` set, they are validated at startup (`ConfigError`): `CABLE_PORT` 0–65535, `CABLE_PATH` starting with `/`, the ping interval and `idle_timeout` as above, `CABLE_MAX_PENDING_BYTES` ≥ 1; and `CABLE` may not set `ping_interval`, `allowed_origins` or `recovery_enabled`, which the settings and `recovery` decide.


## Cable (Bearings)

The default backend, the one the channels addon writes. `CABLE = {"type": "proper.channels.Cable"}` serves the WebSockets with Bearings (the server that runs the app) on `CABLE_PORT`, inside the web process; nothing to install. Channels don't change. A `broadcast()` is one publish to the stream's Bearings topic: one frame, written to every subscriber without Python, using the stream-named broadcast frame of [cable_protocol.md](reference/cable_protocol.md#wire-protocol). Recovery buffers and presence are kept in Python.

- `proper run` starts it (`app.cable.start_server()`, which returns once it listens on `CABLE_PORT` and raises `OSError`, with the reason, when the port can't be listened on; a `host` name that can't be looked up is a `socket.gaierror`) in its web process and stops it with the server (the WebSockets get `shutdown_grace` seconds to close). The web server (Bearings, WSGI) has no WebSockets; the cable's port answers 404 to anything but a WebSocket on `CABLE_PATH`. In production the reverse proxy routes `CABLE_PATH` to `CABLE_PORT` (the blueprint's nginx config has the block); in `DEBUG` the page announces the port in a `<meta name="cable-port">` tag, rendered by `render_importmap()`, and `cable.js` connects to it directly.
- Other processes (`PROCESSES` copies, Huey workers, shells) forward `broadcast()` and `disconnect()` to it, signed, as a `POST` to `CABLE_PATH` on `127.0.0.1:forward_port` (`CABLE_PORT + 1` by default). `app.cable.batch()` works. The cable process answers once it has delivered; a sender that gets no answer in 2 s sends again with the same id, and the copy is ignored.
- Options: `port`, `host` (`0.0.0.0`), `forward_port`, `loops` (4 threads for the sockets; `0` is one per CPU), `workers` (4 threads for channel code), `max_connections` (100000), `max_message` (1 MiB: a larger message from a client closes it, 1009), `max_subscriptions` (0: no limit; past it, `reject_subscription` with `too_many_subscriptions`), `idle_timeout` (60 s), `recovery` (True: keep the last broadcasts of each stream for reconnecting clients), `recovery_buffer_size` (128), `recovery_ttl` (300 s without broadcasts and a stream's buffer is dropped), `recovery_memory_budget` (256 MB for all the buffers; past it, the streams with the oldest last broadcast lose theirs), `presence` (True: who is in each stream, for `track()`), `presence_max_data_size` (4096 bytes of presence data per user, as JSON), `presence_max_members` (0: no limit on who is listed in a stream; past either limit, `track()` raises `ValueError`), `shutdown_grace` (1 s). Any other option is a `TypeError` at startup.
- `app.cable.health()` → `{"serving", "connections", "users", "streams", "server": {"connections", "recovery_enabled", "recovery_topic_count", "recovery_bytes", "presence_enabled", "presence_topics"}}` (`{"serving": False, "connections": 0, "streams": 0}` where nothing is served), for a health endpoint. `app.cable.metrics()` → Prometheus text (`proper_cable_connections`, `proper_cable_streams`, `proper_cable_users`; `""` where nothing is served), also served as `GET /metrics` on the loopback forwarding port `127.0.0.1:CABLE_PORT + 1` by the process that serves the WebSockets, for scraping.
- A client that falls `CABLE_MAX_PENDING_BYTES` behind (it stopped reading) is closed; `cable.js` reconnects and recovers.


## Without Channels (`CABLE = {}`)

The default for an app without the addon: a base `Cable` that serves no WebSockets. A `broadcast()` reaches no one (logged at debug level), and `client.websocket()` raises `RuntimeError` on `connect()`. Setting `CABLE_PORT` with an empty `CABLE` is a `ConfigError` at app setup.


## Several Machines (RedisCable)

`RedisCable` is `Cable` on several machines, with Redis carrying broadcasts between them (`uv add redis`). Code doesn't change, only the config:

```python {title="config/channels.py"}
CABLE = {
    "type": "proper.channels.RedisCable",
    "url": os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    "prefix": "myapp:cable:",   # unique per app sharing a Redis
}
```

- Each machine's web process serves its own WebSockets (Bearings). A `broadcast()` goes straight to the local subscribers of the process that makes it and to Redis; the other machines' web processes deliver it to theirs and skip their own messages.
- Processes without WebSockets (Huey workers, shells) publish to Redis directly: no HTTP forwarding, no `CABLE_PORT + 1`. `disconnect()` reaches every machine too.
- Takes every option of `Cable`. The listener reconnects to Redis on its own, backing off up to 30 s; meanwhile what other machines publish is lost, and a broadcast that can't reach Redis is logged and lost. While no message comes, it PINGs Redis every 30 s (`redis_cable.HEALTH_CHECK_INTERVAL`, with TCP keepalive), so a connection that died without closing is found and replaced. A message in Redis it can't deliver is logged and skipped, without reconnecting.
- Recovery buffers are per machine: a client that reconnects to another machine gets `recovered: false` (use sticky sessions on `CABLE_PATH`).
- Presence is one list in Redis (a hash per stream, `user → {machine: [data, connections, time]}`, changed by a Lua script): join on a user's first connection anywhere, leave on their last; machines refresh an alive key (5 s, TTL 15 s), and one drops a dead machine's users, who leave. Without Redis, each machine lists its own.
- Tests from memory (`client.websocket()`) don't touch Redis.


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

**Client.** `cable.connect()` lives in `application.js`. A page's subscription is tied to an element, so it ends when Turbo Drive swaps the page: a Stimulus controller (loaded by the view with `{#js "js/chat-controller.js" #}`, registered on `window.Stimulus`):

```javascript {title="myapp/assets/js/chat-controller.js"}
import { Controller } from "@hotwired/stimulus"
import { cable } from "cable"

class ChatController extends Controller {
  static targets = ["messages", "input"]
  static values = { room: String }

  connect() {
    this.subscription = cable.subscribe("ChatChannel", { room: this.roomValue }, {
      received: (data) => {
        const el = document.createElement("div")
        el.textContent = data.message
        this.messagesTarget.appendChild(el)
      },
    })
  }

  disconnect() {
    this.subscription.unsubscribe()
  }

  async speak() {
    try {
      await this.subscription.perform("speak", { message: this.inputTarget.value })
      this.inputTarget.value = ""
    } catch (error) {
      alert(error.reason)  // "too_long", "error", "timeout", ...
    }
  }
}

window.Stimulus.register("chat", ChatController)
```

```html+jinja {title="myapp/views/room/show.jx"}
{#js "js/chat-controller.js" #}

<div data-controller="chat" data-chat-room-value="{{ room.name }}">
  <div data-chat-target="messages"></div>
  <input data-chat-target="input">
  <button data-action="chat#speak">Send</button>
</div>
```

For HTML broadcasts, `<turbo-stream-channel>` replaces all of this (see [Turbo Streams](channels.md#turbo-streams)).
