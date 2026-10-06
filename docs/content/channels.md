---
title: Real-Time Updates (Channels)
description: |
  How real-time works in Proper: defining channels, authenticating a connection from the session cookie, subscribing and broadcasting over streams, the cable.js browser client, scaling across workers with Redis, and testing it all.
number_headers: true
---

# Real-Time Updates (Channels)

<section class="admonition wip">
<p class="admonition-title">Work in progress</p>
</section>

Most of a web app is request and response: the browser asks for a page, your code answers, and nothing else happens until the user clicks again. Channels are for the other case - when the *server* needs to speak first. A new chat message should appear for everyone in the room without anyone refreshing; a long import should push its progress; a notification should pop the moment it is created. That two-way, server-initiated traffic runs over a WebSocket, and Channels are how Proper organizes it.

After reading this guide, you will know:

- The three pieces a real-time feature is built from, and how a message travels through them.
- How to define a channel, authenticate the connection, and authorize a subscription.
- How to broadcast - from inside a channel, and from a controller or background task.
- How to use the `cable.js` client, run the cable on several machines with Redis, and test channels without a server.

---

## The shape of a channel

A real-time feature in Proper has three moving parts:

- **The channel** - a Python class, the WebSocket equivalent of a controller. It decides who may subscribe, handles messages from the client, and pushes data back.
- **The cable** - the pub/sub broker. Channels subscribe to named *streams*; when anything broadcasts to a stream, the cable fans the message out to every subscriber. `WseCable` serves the WebSockets of one machine; `RedisCable` is the same cable across several, through Redis.
- **`cable.js`** - the browser client. It opens the one WebSocket, manages your subscriptions, reconnects when the connection drops, and hands incoming data to your callbacks.

The connecting concept is the **stream**: a plain string like `chat_42`. A channel calls `stream_from("chat_42")` to start listening, and any code anywhere calls `broadcast("chat_42", data)` to deliver to every listener. The channel never talks to a specific browser by hand - it talks to a stream, and the cable does the routing.

Here is the whole loop in miniature. A channel that joins a room's stream and re-broadcasts what it is told:

```python {title="channels/chat_channel.py"}
from ..router import router
from .app_channel import AppChannel


@router.channel()
class ChatChannel(AppChannel):
    def subscribed(self):
        self.stream_from(f"chat_{self.params['room']}")

    def speak(self, data):
        self.broadcast(
            f"chat_{self.params['room']}",
            {"message": data["message"]}
        )
```

And the browser side - subscribe, render what arrives, send what the user types:

```javascript
import { cable } from "/cable.js"

cable.connect()
const chat = cable.subscribe(
    "ChatChannel",
    { room: "general" },
    { received(data) { addMessageToDOM(data.message) } }
)

chat.perform("speak", { message: "hello" })
```

Every section below takes one piece of this apart.

---

## Installation

Channels is an addon. Install it with:

```bash
$ proper install channels
```

That creates three things, and adds `proper-wse` to the app's dependencies:

- `config/channels.py` - `CABLE_PATH`, `CABLE_PORT` and the `CABLE` backend config: `WseCable`, which serves the WebSockets from the web process (see [WseCable](#wsecable-the-websockets-on-wse-server) below).
- `channels/app_channel.py` - the `AppChannel` base your own channels inherit from. It is to channels what `AppController` is to controllers.
- `assets/js/cable.js` - the browser client, in the `assets/` folder at the root of the project.

The WebSocket endpoint lives at one path - `/cable` by default - and every channel is multiplexed over it. You never open more than one socket per browser tab, no matter how many channels it subscribes to.

---

## Defining a channel

A channel is a subclass of `AppChannel`, registered with the router by the `@router.channel()` decorator. Use a generator to add one:

```bash
$ proper g channel Chat
```

```python {title="channels/chat_channel.py"}
from ..router import router
from .app_channel import AppChannel


@router.channel()
class ChatChannel(AppChannel):
    def subscribed(self):
        room = self.params["room"]
        self.stream_from(f"chat_{room}")

    def speak(self, data):
        self.broadcast(f"chat_{self.params['room']}", {
            "message": data["message"],
        })
```

The class is registered under its name - `"ChatChannel"` - and that is the name clients subscribe with. The `params` are whatever the client passed when subscribing (here, `{"room": "general"}`); they are available as `.params` for the life of the subscription. The same `params` dict also identifies the subscription: a client can subscribe to `ChatChannel` twice with different rooms, and each `(channel, params)` pair is a separate, independently-addressed subscription.

:::warning
Like controllers, for the `@router.channel()` decorator to run, the module has to be imported somewhere your app loads, so the generator takes care of adding it to `channels/__init__.py`
:::

Inside any channel method you have:

Property         | What it is
---------------- | --------------------
`.params`        | The dict the client sent when subscribing
`.app`           | The `App` - database, config, and the cable
`.channel_name`  | The class name, e.g. `"ChatChannel"`
`.authenticated` | `True` when the connection has a logged-in user
`.request`       | The connection's request, for reading headers and signed cookies

---

## The lifecycle: subscribed and unsubscribed

Two methods bracket a subscription. Override the ones you need:

```python
@router.channel()
class ChatChannel(AppChannel):
    def subscribed(self):
        # Set up streams, authorize, send a welcome.
        self.stream_from(f"chat_{self.params['room']}")
        self.send({"status": "joined"})

    def unsubscribed(self):
        # Clean up anything subscribed() set up outside of streams.
        pass
```

`subscribed()` runs once, when the client subscribes. It is where you check whether the subscription is allowed (see the next section). Call `stream_from()` to start listening, and optionally `send()` an initial message. Anything you `send()` here is buffered and flushed to the client just before the subscription is confirmed. If you `reject()`, the buffered messages are discarded.

`unsubscribed()` runs when the client unsubscribes *or* when the socket closes, including unexpected disconnects. Proper automatically removes the channel from all its streams before calling it, so you only need to undo work that lives elsewhere.

:::warning
`unsubscribed()` is best-effort on disconnect. A clean close calls it but a client closing their browser tab does not. Do not put anything you cannot afford to skip solely in `unsubscribed()`.
:::

---

## Authenticating a connection

A WebSocket handshake is an ordinary HTTP request, so it carries the same cookies your controllers see - including the signed session cookie a logged-in user already has.

Proper uses that: when the auth addon is installed, `AppChannel` is wired to your app's `Session` and `user` models. The logged-in user is exposed as as `current.user`, exactly the way a controller sees it:

```python {title="channels/inbox_channel.py"}
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

`current.user` is the real, server-verified user, and `.authenticated` is the convenience boolean (`current.user is not None`). Because identity is resolved before *every* dispatch, `current.user` is also available inside your action methods, not just `subscribed()`.

This works because of `AppChannel`:

```python {title="channels/app_channel.py"}
from proper.channels import Channel

try:
    from ..models import Session, User
except ImportError:
    Session = None


class AppChannel(Channel):
    Session = Session

    def find_user(self, user_id):
        return User.get_or_none(User.id == user_id)

```

`Session` is used to save the `user_id` to the channel instance when `subscribed()` is called, `find_user` to load the `User` record from the database after that.
If the auth addon is not installed, `Session` is `None`, channels stay anonymous, and `current.user` is `None`.

Authentication is opt-in per connection: a channel with no session model simply never has a user.

The cookie is read once per connection, not once per channel. A page usually opens several subscriptions on its one socket; the first channel that subscribes looks up the session, and the others reuse the user's id it found (they load the user with `find_user`). `current.auth_session` is set only in the `subscribed()` of that first channel.

### Authorizing versus authenticating

Authentication answers *"who is connected?"*; authorization answers *"may they subscribe to this?"*. Do the second in `subscribed()`, using the first:

```python
def subscribed(self):
    room = Room.get_or_none(Room.id == self.params["room_id"])
    if room is None or not room.has_member(current.user):
        self.reject()
        return
    self.stream_from(f"room_{room.id}")
```

`reject()` denies the subscription: the client gets a `reject_subscription` message and the channel is never stored, so none of its actions can be called. Because the stream name is derived from the server-verified `current.user` and a checked membership - not from a client-supplied id - there is no way for a client to listen in on a room it does not belong to.

---

## Actions: messages from the client

Any public method on a channel - anything that is not `subscribed` or `unsubscribed` - can be invoked by the client as an *action*:

```python
@router.channel()
class ChatChannel(AppChannel):
    def subscribed(self):
        self.stream_from(f"chat_{self.params['room']}")

    def speak(self, data):
        self.broadcast(
            f"chat_{self.params['room']}",
            {"message": data["message"], "sender": current.user.login}
        )

    def typing(self, data):
        self.broadcast(
            f"chat_{self.params['room']}",
            {"typing": current.user.login}
        )
```

The client calls `chat.perform("speak", {message: "hello"})` and the matching method runs, with the payload as `data`. Action methods run as regular synchronous Python, with a database connection already open - the same execution model as a controller action.

The framework refuses to call anything that would let a client reach past your intended surface. These are rejected as actions:

Rejected                          | Why
--------------------------------- | ---------------------------------
Names starting with `_`           | Private methods are not part of the action surface
`subscribed`, `unsubscribed`      | Lifecycle hooks, not client-callable
`send`, `broadcast`, `reject`     | Channel internals - calling them from the client would bypass your logic
`stream_from`, `stop_stream_from`, `stop_all_streams` | Stream control belongs to the server
Missing or non-callable names     | There is nothing to run

There is one conventional action name: `receive`. The client's `subscription.send(data)` is shorthand for `perform("receive", data)`, so if you define a `receive(self, data)` method it becomes the default handler for that subscription.

---

## Streams and broadcasting

Streams are the unit of delivery. A channel subscribes to as many as it likes, and broadcasting to a stream reaches every channel - across every connection - that is listening to it.

Method                      | What it does
--------------------------- | -------------------------------
`.stream_from(name)`        | Start listening to a named stream
`.stop_stream_from(name)`   | Stop listening to one stream
`.stop_all_streams()`       | Stop listening to all of them
`.send(data)`               | Send to **this connection only**
`.broadcast(name, data)`    | Send to **every subscriber** of a stream

Use `send()` to answer the one client in front of you (a confirmation, a validation error); use `broadcast()` to tell the room. A broadcast doesn't go through `send()`, even one you override: every subscriber of the stream gets the same data. To tell different users different things, give them different streams, such as `f"user:{user.id}:notices"`.

### Naming streams

Stream names are arbitrary strings, and the convention is a descriptive prefix with a dynamic suffix:

```python
self.stream_from(f"chat_{room_id}")
self.stream_from(f"inbox_{current.user.id}")
self.stream_from(f"document_{doc_id}_edits")
```

The name is the contract between the channel that listens and the code that broadcasts; both sides have to spell it the same way, and there is nothing today that checks they agree.

A typo on one side delivers silently to no one, so a first-class `broadcast_to(model)` that derives the name from a record is on the list in [Where this could grow](#where-this-could-grow).   

### Broadcasting from a controller or a task

The most common broadcast does not come from a channel at all - it comes from an ordinary HTTP request or a background job that just changed something the live page should see. Any code with the app in hand can reach the cable through `app.cable`:

```python {title="controllers/message_controller.py"}
# 
from ..models import Message
from ..router import router
from .app_controller import AppController


@router.resource("rooms/:room_id/messages")
class MessageController(AppController):
    def create(self):
        room_id = self.params["room_id"]
        message = Message.create(room_id=room_id, text=self.params["text"])

        # Push to everyone watching this room,
        # then answer this request normally.
        self.app.cable.broadcast(f"chat_{room_id}", {
            "message": message.text,
            "id": message.id,
        })

        self.response.redirect_to("Message.index", room_id=room_id)
```

A controller reaches it through `.app.cable`; a background task imports the app, or uses the `current.app` proxy:

```python
# tasks/__init__.py
from ..main import app


@app.queue.task()
def notify_user(user_id, payload):
    app.cable.broadcast(f"inbox_{user_id}", payload)
```

This is the seam between the request world and the live one: the controller persists the message and redirects as usual, and the broadcast is a side note that lights up every open page. [Background Tasks](/docs/tasks) covers running the worker that the second example needs.

When a request makes several broadcasts, wrap them in `app.cable.batch()`. From a process that doesn't serve the WebSockets, such as a task worker, each broadcast is a request to the one that does (see [WseCable](#wsecable-the-websockets-on-wse-server)); inside a batch they all travel in one:

```python
with self.app.cable.batch():
    self.app.cable.broadcast(f"room_{room.id}", html)
    for user_id in member_ids:
        self.app.cable.broadcast(f"unreads_{user_id}", {"room_id": room.id})
```

### Closing a user's connections

A channel authorizes when it subscribes. If you then take that access away - remove someone from a room, ban them, sign them out - their open subscriptions keep receiving until they disconnect. `app.cable.disconnect(user_id=...)` closes every connection of that user, in whichever process holds it. Their pages reconnect and subscribe again, and the channels that no longer authorize them reject the subscription:

```python
membership.delete_instance()
self.app.cable.disconnect(user_id=membership.user_id)
```

---

## Tracking who is connected

Channels do not ship a presence API, but the lifecycle hooks give you the raw material for one: increment a count (or add to a set) in `subscribed()`, undo it in `unsubscribed()`, and broadcast the change so everyone's roster updates.

```python
@router.channel()
class RoomChannel(AppChannel):
    def subscribed(self):
        if not self.authenticated:
            self.reject()
            return
        self.room = f"room_{self.params['room_id']}"
        self.stream_from(self.room)
        self.broadcast(
            self.room,
            {"event": "joined", "user": current.user.login},
        )

    def unsubscribed(self):
        self.broadcast(
            self.room,
            {"event": "left", "user": current.user.login},
        )
```

That is enough for join/leave notices and "X is typing". Be honest with yourself about its limits, though:

- It tells you about *events* (someone joined, someone left), not *state* (who is here right now). For a live roster you have to track membership yourself in a shared store.
- A user with three tabs counts as three joins. Deduplicating by user is on you.
- `unsubscribed()` is best-effort, so a hard disconnect can leak a "ghost" member that never leaves.
- Across multiple machines it gets harder: `RedisCable` relays *broadcasts* between machines, not membership *state*, so a roster kept in one worker's memory does not see users on another. A correct multi-worker roster needs a shared store (a Redis set per room) with a heartbeat to expire the ghosts.

A built-in presence primitive that handles the multi-tab and multi-worker cases is the most-requested thing Channels does not yet have - see [Where this could grow](#where-this-could-grow).

---

## The client: cable.js

The generated `cable.js` is an ES module that owns the single connection, your subscriptions, and reconnection. It is already in your `importmap` so you can import it directly:

```javascript
import { cable } from "/cable.js"

cable.connect()

const chat = cable.subscribe("ChatChannel", { room: "general" }, {
  connected()    { console.log("subscribed") },
  disconnected() { console.log("connection lost") },
  rejected()     { console.log("subscription denied") },
  received(data) { addMessageToDOM(data) },
})

chat.perform("speak", { message: "hello" })  // invoke an action
chat.send({ message: "hello" })  // shorthand for perform("receive", data)
chat.unsubscribe()               // leave this channel
cable.disconnect()               // close the socket, stop reconnecting
```

`cable.connect()` takes an optional URL; with none, it points at `/cable` on the current host (`ws://` on http, `wss://` on https).

If you change `CABLE_PATH`, pass the matching URL to `connect()`. `cable.subscribe(channel, params, callbacks)` returns a subscription; if you pass only two arguments and the second looks like a callbacks object, it is treated as callbacks with empty params.

The four callbacks - `connected`, `disconnected`, `received`, `rejected` - are all optional.

When the connection drops, `cable.js` reconnects on its own with exponential backoff (1s, 2s, 4s, up to ten attempts) and re-subscribes everything automatically, so a brief network blip is invisible to your code. `cable.disconnect()` is what stops it.

Because everything is multiplexed, holding several subscriptions is normal and cheap:

```javascript
const general = cable.subscribe(
    "ChatChannel", { room: "general" }, { received: render })
const random  = cable.subscribe(
    "ChatChannel", { room: "random" },  { received: render })
const inbox   = cable.subscribe(
    "InboxChannel", { received: showToast })
```

Each is keyed by its channel name plus params, which is how an incoming broadcast finds the right `received` callback.

---

## Broadcasting HTML (Turbo Streams)

The broadcasts so far ship JSON, leaving the `received()` callback to rebuild the DOM by hand - re-implementing in JavaScript the markup you already have as a Jx component.

Proper bundles [Turbo](https://turbo.hotwired.dev/), so you can instead broadcast the *rendered* component wrapped in a `<turbo-stream>` and let Turbo apply it - a live-updating list then needs no custom JavaScript at all.

A `<turbo-stream>` is HTML that names a DOM operation and a target:

```html
<turbo-stream action="append" target="messages">
  <template><li>Ana: hello</li></template>
</turbo-stream>
```

The `turbo_stream` builder has a method per action; each builds one from a Jx component, or from raw HTML:

```python
from proper import turbo_stream

turbo_stream.append(
    "messages",       # the id of the element to update
    "message.jx",     # the component to render
    message=message,  # arguments for the component
)
# -> <turbo-stream action="append" target="messages">
#      <template>...</template>
#    </turbo-stream>
```

The first argument is the id of the element to act on, and the method name is the operation. Turbo knows several:

Action               | Effect
-------------------- | ---------------------------------------------------------
`append` / `prepend` | Add the fragment as the last / first child of the target
`before` / `after`   | Insert the fragment as a sibling before / after the target
`replace`            | Swap the target element itself
`update`             | Replace the target's contents, keep the element
`remove`             | Remove the target (no `<template>` needed)
`morph`              | Update the target by morphing, preserving unchanged nodes

Broadcast it like any other payload:

```python {title="controllers/message_controller.py"}
def create(self):
    room_id = self.params["room_id"]
    message = Message.create(
        room_id=room_id,
        text=self.params["text"],
        author=current.user
    )

    self.app.cable.broadcast(
        f"chat_{room_id}",
        turbo_stream.append(
            "messages",       # the id of the element to update
            "message.jx",     # the component to render
            message=message,  # arguments for the component
        ),
    )
    self.response.redirect_to("Message.index", room_id=room_id)
```

You don't need to write JavaScript to subscribe a page to the channel, just use the custom element `<turbo-stream-channel>` (it was added by `cable.js`):

```html+jinja {title="views/message/index.jx", hl_lines="3-4"}
{#import "message.jx" as Message #}

<turbo-stream-channel channel="ChatChannel" params='{"room_id": 42}'>
</turbo-stream-channel>

...

<ul id="messages">
  {% for message in messages %}
    <Message message={{ message }} />
  {% endfor %}
</ul>
```

The element subscribes through `cable.js` and feeds every frame to Turbo, which appends the new `<li>` for you. The same `Message` component renders the initial list and every live update, so there is one source of truth for the markup.

For an imperative subscription, `import { streamFrom } from "cable"` and call `streamFrom("ChatChannel", { room_id: 42 })`.

Authorization is unchanged: the client sends `params`, never a stream name. The channel's `subscribed()` still authorizes with `reject()` (see [Authorizing versus authenticating](#authorizing-versus-authenticating)) and derives the stream name on the server, so the Turbo wiring opens no new door.

:::note
The same fragment can also be returned from a controller. Set the response mimetype to `"text/vnd.turbo-stream.html"`, and Turbo will apply the operations to a plain form submit, with no full-page reload. Concatenate several streams to send more than one operation at once.
:::

---

## The wire protocol

`cable.js` speaks this so you do not have to, but the frames are worth knowing for debugging or for writing a non-JavaScript client. Every message is JSON over the `/cable` WebSocket.

The client sends three commands - `subscribe`, `message` (invoke an action), and `unsubscribe`:

```json
{ "command": "subscribe", "channel": "ChatChannel",
    "params": {"room": "general"} }

{ "command": "message", "channel": "ChatChannel",
    "params": {"room": "general"}, "action": "speak",
    "data": {"message": "hi"} }

{ "command": "unsubscribe", "channel": "ChatChannel",
    "params": {"room": "general"} }
```

The server sends back `confirm_subscription`, `reject_subscription`, `message` (the payload of a `send()`), `broadcast` (the payload of a `broadcast()`), and `error`:

```json
{ "type": "confirm_subscription", "channel": "ChatChannel",
    "params": {"room": "general"}, "streams": ["chat:general"] }

{ "type": "reject_subscription", "channel": "ChatChannel",
    "params": {"room": "general"} }

{ "type": "message", "channel": "ChatChannel",
    "params": {"room": "general"}, "data": {"message": "hi"} }

{ "c": "P", "type": "broadcast", "stream": "chat:general",
    "data": {"message": "hi"} }

{ "type": "error", "reason": "not_subscribed" }
```

A `reject_subscription` carries `"reason": "unknown_channel"` when no channel by that name is registered; a subscription your own `reject()` turned away has no reason.

An `error` carries a `reason`, one of: `invalid_json`, `unknown_command`, `not_subscribed`, `invalid_action`, `unknown_action`, and `invalid_message` (JSON that is not an object).

Every few seconds the server sends a ping, which the client uses to tell a dead connection from a quiet one; `message` is the server's time:

```json
{ "type": "ping", "message": 1791230000 }
```

The cable writes one frame per broadcast for every subscriber, so it can't put each subscription's `channel` and `params` in it. A `broadcast` names the stream instead, and `confirm_subscription` lists the streams of the subscription, so the client delivers the broadcast to every subscription streaming from it. The `c` field is wse's message category; ignore it.

The handshake itself is refused, with a 403, when it comes from another site's page: see `CABLE_ALLOWED_ORIGINS` below.


---

## WseCable: the WebSockets on wse-server

This is the backend the channels addon configures. `WseCable` serves the WebSockets with [proper-wse](https://github.com/jpsca/proper-wse), our fork of [wse-server](https://github.com/silvermpx/wse), a server written in Rust (tokio and tungstenite), inside the web process. Channels keep their API: `subscribed()`, the actions and `unsubscribed()` run in Python, in a pool of threads, in order for each connection. What changes is underneath: a stream is a wse topic, and a `broadcast()` hands the encoded frame to wse, which writes it to every subscriber without going back to Python. With thousands of clients on one stream this is the backend that keeps up.

```python {title="config/channels.py"}
CABLE = {"type": "proper.channels.wse.WseCable"}  # serves on CABLE_PORT
```

Install it with the `wse` extra (`uv add "proper[wse]"`), which brings `proper-wse`, with wheels for free-threaded Python (3.14t) as well. It imports as `wse_server`, so don't install the original `wse-server` next to it.

- `proper run` starts the server, in its web process, before the first request, and stops it with the server. The web server itself (Granian, over WSGI) has no WebSockets. Under another server, call `app.cable.start_server()` and `app.cable.stop_server()` yourself.
- Every other process that loads the app has no WebSockets: the other copies of `PROCESSES`, a Huey worker, a shell. Their `broadcast()`s and `disconnect()`s are forwarded to the serving process, signed with the app's secret keys, as a `POST` to `CABLE_PATH` on `127.0.0.1:forward_port` (`CABLE_PORT + 1` unless given). `app.cable.batch()` sends several in one request.
- Broadcasts use the stream-named frames of the wire protocol above; `cable.js` understands them.
- The server pings every connection each `CABLE_PING_INTERVAL` seconds. A client that stops reading is closed, without the close handshake it would never let through, and `cable.js` reconnects: once more than `CABLE_MAX_PENDING_BYTES` (4 MB) are waiting for it and nothing got through in `CABLE_STALL_TIMEOUT` seconds (10), or ten times as many are waiting. Keep ten times `CABLE_MAX_PENDING_BYTES` below `max_outbound_queue_bytes`, where wse drops broadcasts for a connection instead.
- The original wse-server is refused at startup: refusing other sites' origins and waiting for delivery need `proper-wse`.

In production, your reverse proxy routes `CABLE_PATH` to `CABLE_PORT`; the blueprint's nginx config has the block ready. In development there is no proxy, so the page tells the browser where the cable is: `render_importmap()` adds a `<meta name="cable-port">` tag when `DEBUG` is on, and `cable.js` connects to that port on the same host.

Option                     | Default    | What it is
-------------------------- |----------- | -----------------------------
`port`                     | `CABLE_PORT` | Port of the WebSockets
`host`                     | `0.0.0.0`  | Address to listen on
`forward_port`             | `port + 1` | Port, on 127.0.0.1, of the broadcasts other processes forward
`workers`                  | `4`        | Threads that run the channels' code
`max_connections`          | `100000`   | Connections wse accepts
`max_outbound_queue_bytes` | 64 MB      | How far behind a connection can fall before wse drops broadcasts for it. A broadcast frame is shared by every connection it goes to, so a backlog costs memory once, not once per connection
`backpressure_bytes`       | 128 KB     | A `broadcast()` waits while the subscribers of its stream have more than this queued, on average. Whoever publishes slows down to the pace of delivery, so messages don't pile up and arrive late. Higher: more messages per second under load, and more latency. `0` never waits
`backpressure_timeout`     | `1.0`      | Longest a `broadcast()` waits, in seconds; then it is sent anyway

Any other option goes to `wse_server.RustWSEServer`, such as `max_pending_handshakes` (how many handshakes may be in progress at once; raise it if thousands of clients can reconnect together, after a restart).

---

## Several machines: RedisCable

`WseCable` serves the WebSockets of one machine. To run the app on several, behind a load balancer, use `RedisCable`: the same cable, with Redis carrying the broadcasts between machines. The channels and your code don't change, only the config:

```python {title="config/channels.py"}
CABLE = {
    "type": "proper.channels.RedisCable",
    "url": os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    "prefix": "myapp:cable:",
}
```

Each machine's web process serves its own WebSockets, as with `WseCable`. A `broadcast()` goes straight to the subscribers of the process that makes it, if it serves any, and to Redis, where the web processes of the other machines get it and hand it to theirs; each one skips what it published itself. A process without WebSockets - a task worker, a shell - only publishes to Redis, so there is no forwarding over HTTP and no `CABLE_PORT + 1`. `disconnect()` reaches every machine the same way.

Option   | Default                      | What it is
-------- |----------------------------- | -----------------------------
`url`    | `redis://localhost:6379/0`   | Redis connection URL
`prefix` | `proper:cable:`              | Namespace of its Redis channel; give each app its own if several share one Redis

It takes every option of `WseCable` as well. It needs the `redis` package (`uv add redis`) and raises when it is configured without it. Each web process subscribes when `proper run` starts it, waiting up to a second so that what is published right away isn't missed; if the Redis connection drops, it reconnects with backoff (up to 30 s). Meanwhile its own clients still get their own broadcasts, and a broadcast that can't reach Redis is lost with a warning; the page that made it still renders. Waiting for delivery (`backpressure_bytes`) only sees the machine that publishes. Tests that use `client.websocket()` run the cable from memory, without Redis.

The line to remember: `RedisCable` shares *broadcasts* across machines, not *state*. Fire-and-forget delivery crosses the cluster cleanly. Anything that needs a shared, durable view - a presence roster, a "replay the last value to a late subscriber" - is not something the cable does for you, because Redis pub/sub carries events, not memory. [Deployment](/docs/deployment) covers choosing a worker count and running the server.

## Checking where a WebSocket comes from

Browsers send a site's cookies with any WebSocket to it, even one opened by a page of another site, so the cable checks the handshake's `Origin`. It accepts a handshake with no `Origin` (not a browser), one from the `Host` it was sent to or from the app's `HOST`, and in `DEBUG` one from any port of the same host name (the page and the cable listen on different ports there). Any other origin gets a 403, unless you list it:

```python {title="config/channels.py"}
CABLE_ALLOWED_ORIGINS = ["https://admin.example.com"]
```

## Without channels

An app without the channels addon has `CABLE = {}`: a `Cable` that serves no WebSockets, so a `broadcast()` reaches no one (it is logged at the debug level). Setting `CABLE_PORT` with an empty `CABLE` is a `ConfigError` when the app starts.

---

## Testing channels

You do not need a running server to test a channel. The test client opens a WebSocket session, served from memory, that drives `subscribe`, actions, and disconnect, and lets you assert on the frames that come back:

```python
import pytest

# Requires `pytest-asyncio` to run
@pytest.mark.asyncio
async def test_chat_broadcasts_to_the_room(client):
    ws = client.websocket()
    task = await ws.connect()

    confirm = await ws.subscribe("ChatChannel", room="general")
    assert confirm["type"] == "confirm_subscription"

    await ws.send_action(
        "ChatChannel",
        "speak",
        {"message": "hi"},
        room="general"
    )
    msg = await ws.receive()
    assert msg["data"]["message"] == "hi"

    await ws.close()
    await task
```

`client.websocket()` returns a session; `connect()` opens the connection and returns a task you await after `close()`; `receive_raw()` shows the handshake's answer, `{"type": "accept"}`, which `receive()` and `subscribe()` skip. `subscribe()` sends a subscribe command and returns the response, `send_action()` invokes an action, and `receive()` returns the next frame parsed from JSON.

The session runs the cable from memory instead of a port (`app.cable.serve_in_memory()`): no server, no threads, and each event runs right away through the cable's own code. The same test works with `WseCable` and `RedisCable`, which doesn't touch Redis from memory. With an app whose cable serves no WebSockets (`CABLE = {}`), `connect()` raises a `RuntimeError`.

To test an authenticated channel, sign a user in first - the test client carries the same session cookie into the handshake that an HTTP request would. The [Testing guide](/docs/testing) covers the `TestClient` and `sign_in()` in full.

:::note
As you can see, testing channels is one of the few places where the well-hidden `async` nature of Proper leaks into __your__ code. Sorry about that.
:::

---

## A full example

A complete room chat: an authenticated channel, a controller that persists a message and broadcasts it, and the page that ties them together.

```python {title="channels/chat_channel.py"}
from proper import current

from ..models import Room
from ..router import router
from .app_channel import AppChannel


@router.channel()
class ChatChannel(AppChannel):
    def subscribed(self):
        room = Room.get_or_none(Room.id == self.params["room_id"])
        if (
            room is None
            or not self.authenticated
            or not room.has_member(current.user)
        ):
            self.reject()
            return
        self.stream_from(f"chat_{room.id}")

    def speak(self, data):
        self.broadcast(f"chat_{self.params['room_id']}", {
            "message": data["message"],
            "sender": current.user.login,
        })
```

```python {title="controllers/message_controller.py"}
from ..models import Message
from ..router import router
from .app_controller import AppController


@router.resource("rooms/:room_id/messages")
class MessageController(AppController):
    def create(self):
        room_id = self.params["room_id"]
        message = Message.create(
            room_id=room_id,
            author=current.user,
            text=self.params["text"],
        )
        self.app.cable.broadcast(f"chat_{room_id}", {
            "message": message.text,
            "sender": message.author.login,
        })
        self.response.redirect_to("Message.index", room_id=room_id)
```

```javascript {title="the room page"}
import { cable } from "/cable.js"

cable.connect()

const chat = cable.subscribe(
    "ChatChannel",
    { room_id: ROOM_ID },
    {
        received({ message, sender }) {
            const el = document.createElement("li")
            el.textContent = `${sender}: ${message}`
            document.getElementById("messages").append(el)
        },
    }
)

document.getElementById("composer").addEventListener(
    "submit",
    (e) => {
        e.preventDefault()
        const input = e.target.elements.message
        chat.perform("speak", { message: input.value })
        input.value = ""
    }
)
```

The channel guards the room with the server-verified user; the controller is the system of record that persists and broadcasts; the page renders whatever arrives. A message a user sends through the form is saved by the controller and lit up on every open page by the broadcast.

---

## Where this could grow

Channels covers the durable core - a multiplexed connection, authenticated subscriptions, streams, broadcasting, a reconnecting client, and a Redis backend for scale. Several things that mature real-time stacks offer are not here yet. None of them block you - workarounds exist - but they are the obvious places the framework will grow.

- **A presence primitive.** A real who-is-online API that handles the multi-tab and multi-worker cases (a Redis-backed roster with heartbeat expiry) instead of the manual, single-worker pattern shown above.
- **Model-derived stream names.** `broadcast_to(record, data)` and `stream_for(record)` that derive a stable stream name from a model, removing the stringly-typed names that a typo can silently break.
- **A subscription reply.** Letting an action return a value the framework sends back to the caller, tagged to that call, so optimistic UIs can confirm success or surface a validation error without a separate correlated message.
- **Per-subscription timers.** A `periodically(...)` hook for server-driven pushes - live counters, clocks, dashboards - scoped to the subscription's lifetime. For now, a periodic background task that broadcasts to a stream covers most of this.
- **Channel error hooks.** A `rescue_from`-style way to turn an exception in an action into a clean error frame for the client, rather than only logging it.

If you build any of these against the current code, the framework would love a PR.

---

## What's next

Channels touches several other parts of Proper:

- [Authentication](/docs/authentication) - the session and signed-cookie model that `AppChannel` reuses to put `current.user` on a connection.
- [Background Tasks](/docs/tasks) - the worker process behind broadcasting from a job, plus scheduling and retries.
- [Jx Components](/docs/jx_components) - the server-rendered components you wrap in a `<turbo-stream>` to broadcast.
- [Deployment](/docs/deployment) - workers, processes and the cable port behind a proxy, and running Redis so `RedisCable` can carry broadcasts across machines.
