---
title: Channels
description: Channels addon — WebSocket system with multiplexed channels, streams, and broadcasting
last_verified: 2026-04-02
---

# Channels

Proper Channels is an installable addon that provide a channel-based WebSocket system for real-time communication. All WebSocket traffic is multiplexed over a single endpoint (`/cable` by default). Clients subscribe to named channels, and channels can broadcast messages to all subscribers of a stream.

The system has three layers:

| Layer       | Module            | Role                                                          |
|-------------|-------------------|---------------------------------------------------------------|
| **Channel** | `proper.channel`  | Base class you subclass — the "controller" for WebSockets     |
| **Cable**   | `proper.cable`    | Pub/sub broker — maps stream names to channels                |
| **AppWs**   | `proper.app_ws`   | ASGI handler — protocol parsing, multiplexing, lifecycle      |

Channel code is regular sync Python. The framework handles the async boundary the same way it does for HTTP requests: channel methods run in threads via `asyncio.to_thread()`, with database connections managed automatically.

## Table of Contents

- [Installation](#installation)
- [Defining Channels](#defining-channels)
- [Channel Lifecycle](#channel-lifecycle)
- [Action Methods](#action-methods)
- [Streams and Broadcasting](#streams-and-broadcasting)
- [Channel Properties](#channel-properties)
- [Client-Side Usage](#client-side-usage)
- [Wire Protocol](#wire-protocol)
- [Configuration](#configuration)
- [Scaling with Redis](#scaling-with-redis)
- [Full Example](#full-example)


## Installation

Install the channels addon with:

```bash
proper install channels
```

This creates:

- `config/channels.py` file
- Adds `cable.js` to your `assets/js` folder


## Defining Channels

A channel is a subclass of `Channel`, registered with the router using the `@router.channel()` decorator. Channels are the WebSocket equivalent of controllers.

```python {title="myapp/channels/chat_channel.py"}
from proper.channel import Channel
from ..router import router


@router.channel()
class ChatChannel(Channel):
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
    if not self.params.get("token"):
        self.reject()
        return
    self.stream_from(f"notifications_{self.params['user_id']}")
    self.send({"greeting": "welcome!"})
```

Messages sent during `subscribed()` are buffered and flushed to the client before the subscription confirmation. If the channel calls `self.reject()`, the buffered messages are discarded.

### `unsubscribed()`

Called when the client explicitly unsubscribes or when the WebSocket connection closes (including unexpected disconnects). Use it for cleanup. The framework automatically removes the channel from all streams before calling this method.

### Rejection

Call `self.reject()` inside `subscribed()` to deny the subscription. The client receives a `reject_subscription` message and the channel is not stored.

```python
def subscribed(self):
    user = authenticate(self.params.get("token"))
    if not user:
        self.reject()
        return
    self.stream_from(f"user_{user.id}")
```


## Action Methods

Any public method on a channel (other than `subscribed` and `unsubscribed`) can be invoked by the client as an action. The client sends a `message` command with an `action` name and optional `data`.

```python
@router.channel()
class ChatChannel(Channel):
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
- `subscribed` and `unsubscribed` (lifecycle-only)
- Empty action names
- Methods that don't exist or aren't callable


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

### Stream Naming

Stream names are arbitrary strings. The convention is to use a descriptive prefix and a dynamic suffix:

```python
self.stream_from(f"chat_{room_id}")
self.stream_from(f"notifications_{user_id}")
self.stream_from(f"document_{doc_id}_edits")
```

### Broadcasting from Outside a Channel

Any part of the application can broadcast to a stream via `app.cable`. This is the key integration point between HTTP and WebSocket: controllers and background tasks can push real-time updates to connected clients.

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


## Channel Properties

Inside any channel method, the following are available:

| Property          | Description                                                |
|-------------------|------------------------------------------------------------|
| `self.app`        | The `App` instance (access DB, config, cable, etc.)        |
| `self.params`     | Dict of params the client sent when subscribing            |
| `self.channel_name` | The class name (e.g. `"ChatChannel"`)                   |


## Client-Side Usage

The generated app includes `cable.js`, an ES module that handles the WebSocket protocol, subscription management, and automatic reconnection.

### Basic Usage

```javascript
import { cable } from "./cable.js"

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

On disconnect, `cable.js` reconnects with exponential backoff (1s, 2s, 4s, ...) up to 10 attempts. On reconnect, all existing subscriptions are automatically re-subscribed. Call `cable.disconnect()` to stop reconnection.

### Multiple Subscriptions

A single WebSocket connection can hold multiple subscriptions — to different channels or to the same channel with different params:

```javascript
const general = cable.subscribe("ChatChannel", { room: "general" }, { ... })
const random  = cable.subscribe("ChatChannel", { room: "random" }, { ... })
const notifications = cable.subscribe("NotificationChannel", { ... })
```

Each subscription is identified by its channel name + params combination.

### Loading cable.js

Add the script to your layout:

```html+jinja {title="myapp/views/layouts/app.jx"}
<script src="{{ url_for('assets', file='js/cable.js') }}" type="module"></script>
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

**Subscription confirmed:**

```json
{"type": "confirm_subscription", "channel": "ChatChannel", "params": {"room": "general"}}
```

**Subscription rejected:**

```json
{"type": "reject_subscription", "channel": "ChatChannel", "params": {"room": "general"}}
```

**Data message (from `send()` or `broadcast()`):**

```json
{"type": "message", "channel": "ChatChannel", "params": {"room": "general"}, "data": {"message": "hello"}}
```

**Error:**

```json
{"type": "error", "reason": "not_subscribed"}
```

Error reasons: `invalid_json`, `unknown_command`, `not_subscribed`, `invalid_action`, `unknown_action`.


## Configuration

| Setting      | Default    | Description                        |
|--------------|------------|------------------------------------|
| `CABLE_PATH` | `"/cable"` | WebSocket endpoint path            |

Set in your app config:

```python {title="myapp/config/main.py"}
CABLE_PATH = "/ws"
```


## Scaling with Redis

The default `Cable` backend is an in-process pub/sub broker. Broadcasts from one process do not reach clients connected to a different process. For single-process deployments (one Uvicorn worker) this is fine.

For multi-process deployments, use `RedisCable` — a Redis-backed backend that relays broadcasts across workers via Redis pub/sub.


### How It Works

1. When any code calls `cable.broadcast(stream, data)`, `RedisCable` publishes the message to a Redis pub/sub channel.
2. A background listener in each process receives the message via a pattern subscription (`psubscribe`).
3. The listener delivers the message to all local channels subscribed to that stream.

This means every process — including the one that published — receives the message through Redis, ensuring consistent delivery.


### Configuration

Set the `CHANNELS` dict in your config to enable `RedisCable`:

```python {title="myapp/config/channels.py"}
import os

env = os.getenv("APP_ENV", "dev")

CHANNELS = {}

if env == "prod":
    CHANNELS = {
        "type": "proper.cable.RedisCable",
        "url": os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        "prefix": "myapp:cable:",
    }
```

When `CHANNELS` is empty (or not set), the framework uses the default in-memory `Cable`.

| Option   | Default                    | Description                                         |
|----------|----------------------------|-----------------------------------------------------|
| `type`   | —                          | Class path, e.g. `"proper.cable.RedisCable"`        |
| `url`    | `redis://localhost:6379/0` | Redis connection URL                                |
| `prefix` | `proper:cable:`            | Prefix for Redis pub/sub channel names              |

The `prefix` prevents collisions when multiple apps share the same Redis instance. Each app should use a unique prefix.


### Requirements

`RedisCable` requires the `redis` package:

```bash
uv add redis
```

An `ImportError` is raised at startup if `redis` is not installed and `CHANNELS` is configured to use `RedisCable`.


### Lifecycle

`RedisCable` hooks into the ASGI lifespan automatically:

- **Startup** — starts a background listener task that subscribes to Redis and delivers messages to local channels.
- **Shutdown** — cancels the listener and closes all Redis connections.

No manual setup is needed beyond the config.


### Reconnection

If the Redis connection drops (server restart, network issue), the listener reconnects automatically with exponential backoff (1s, 2s, 4s, ... up to 30s). Once reconnected, it re-subscribes and resumes delivery. No messages are lost for clients connected to the same process; messages published while disconnected are missed (this is inherent to Redis pub/sub).


### Usage

Application code does not change when switching from `Cable` to `RedisCable`. Broadcasting works the same way:

```python
# From a channel
self.broadcast(f"chat_{room_id}", {"message": text})

# From a controller or task
app.cable.broadcast(f"chat_{room_id}", {"message": text})
```


## Full Example

A complete chat feature with a channel, a controller that broadcasts on message creation, and the client-side code.

**Channel:**

```python {title="myapp/channels/chat_channel.py"}
from proper.channel import Channel
from ..router import router


@router.channel()
class ChatChannel(Channel):
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
import { cable } from "./cable.js"

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
