---
title: Real-Time Updates (Channels)
description: |
  How real-time works in Proper: defining channels, authenticating a connection from the session cookie, subscribing and broadcasting over streams, the cable.js browser client, Turbo Streams over the cable, the cable server, recovery of missed broadcasts, and testing it all.
number_headers: true
---

# Real-Time Updates (Channels)

<section class="admonition wip">
<p class="admonition-title">Work in progress</p>
</section>

Most of a web app is request and response: the browser asks for a page, your code answers, and nothing else happens until the user clicks again. Channels are for the other case - when the *server* needs to speak first. A new chat message should appear for everyone in the room without anyone refreshing; a long import should push its progress; a notification should pop the moment it is created. That server-initiated traffic runs over a WebSocket, and Channels are how Proper organizes it.

After reading this guide, you will know:

- The three pieces a real-time feature is built from, and how a message travels through them.
- How to define a channel, authenticate the connection, and authorize a subscription.
- How to broadcast - from inside a channel, and from a controller or background task.
- How to use the `cable.js` client, or skip JavaScript entirely with Turbo Streams.
- How the WebSockets are served, and how to test channels without a server.

---

## The shape of a channel

A real-time feature in Proper has three parts:

- **The channel** - a Python class, the WebSocket equivalent of a controller. It decides who may subscribe, handles messages from the client, and sends data back.
- **The cable** - the server that holds the WebSocket connections and delivers messages. Channels subscribe to named *streams*; when any code broadcasts to a stream, the cable sends the message to every subscriber.
- **`cable.js`** - the browser client. It opens one WebSocket, manages your subscriptions, reconnects when the connection drops, and hands incoming data to your callbacks.

What connects them is the **stream**: a plain string like `chat_42`. A channel calls `stream_from("chat_42")` to start listening, and any code anywhere calls `broadcast("chat_42", data)` to deliver to every listener. The channel never addresses a specific browser - it addresses a stream, and the cable does the routing.

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
            {"message": data["message"]},
        )
```

And the browser side - subscribe, render what arrives, send what the user types:

```javascript
import { cable } from "cable"

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

It adds `proper-wse` to the app's dependencies (the WebSocket server, see [The cable server](#the-cable-server-wsecable)) and creates:

- `config/channels.py` - `CABLE_PATH`, `CABLE_PORT`, and `CABLE`, the cable backend. It is imported from `config/__init__.py`.
- `channels/app_channel.py` - the `AppChannel` base your own channels inherit from. It is to channels what `AppController` is to controllers.
- `channels/__init__.py` - where each channel module is imported, so its `@router.channel()` decorator runs.
- `assets/js/cable.js` - the browser client. It is added to the import map as `"cable"`, and `assets/js/application.js` imports it, so every page can use it.
- `tests/channels/` - for your channel tests.

That is all the setup there is. `proper run` starts the cable in the web process, on `CABLE_PORT` - `PORT + 1` by default, so `2301` in development. All the channels of a page share one WebSocket: a browser tab never opens more than one, however many channels it subscribes to.

---

## Defining a channel

A channel is a subclass of `AppChannel`, registered with the router by the `@router.channel()` decorator. Use the generator to add one:

```bash
$ proper g channel Chat
```

It creates `channels/chat_channel.py` and imports it from `channels/__init__.py`. Fill it in:

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

The channel is registered under its class name - `"ChatChannel"` - and that is the name clients subscribe with. To register it under another name, pass it to the decorator: `@router.channel("chat")`.

The `params` are whatever the client passed when subscribing (here, `{"room": "general"}`), available as `self.params` for the life of the subscription. The channel name and the `params` together identify a subscription: a client can subscribe to `ChatChannel` twice with different rooms, and each one is a separate subscription, with its own channel instance.

:::warning
Like controllers, the `@router.channel()` decorator only runs if the module is imported. The generator adds the import to `channels/__init__.py`; if you create a channel file by hand, add it there yourself.
:::

Inside any channel method you have:

Property         | What it is
---------------- | --------------------
`.params`        | The dict the client sent when subscribing
`.app`           | The `App` - config, the cable, and the rest
`.channel_name`  | The name it was registered under, e.g. `"ChatChannel"`
`.authenticated` | `True` when the connection has a logged-in user
`.user_id`       | The id of that user, or `None`
`.request`       | The WebSocket handshake, for reading headers and signed cookies

---

## The lifecycle: subscribed and unsubscribed

Two methods bracket a subscription. Override the ones you need:

```python
@router.channel()
class ChatChannel(AppChannel):
    def subscribed(self):
        # Authorize, set up streams, send a welcome.
        self.stream_from(f"chat_{self.params['room']}")
        self.send({"status": "joined"})

    def unsubscribed(self):
        # Clean up anything subscribed() set up outside of streams.
        pass
```

`subscribed()` runs once, when the client subscribes. It is where you decide whether the subscription is allowed (see [Authorizing versus authenticating](#authorizing-versus-authenticating)). Call `stream_from()` to start listening, and optionally `send()` a first message. What you `send()` here is held back and delivered just before the subscription is confirmed; if you `reject()`, it is discarded and never reaches the client.

`unsubscribed()` runs when the client unsubscribes, when the connection closes - the tab was closed, the network dropped, or the server closed it - and when the server stops. Proper removes the channel from all its streams before calling it, so you only need to undo work that lives elsewhere.

:::warning
`unsubscribed()` does not run if the server process is killed or crashes, and for a connection that dies without closing (a laptop that went to sleep) it runs late: when the server notices the silence, about a minute later. Do not keep anything you cannot afford to lose solely in what `unsubscribed()` cleans up.
:::

---

## Authenticating a connection

A WebSocket handshake is an ordinary HTTP request, so it carries the same cookies your controllers see - including the signed session cookie of a logged-in user.

When the [auth addon](/docs/authentication) is installed, `AppChannel` uses that cookie to find the user, and exposes it as `current.user`, the same way a controller sees it:

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

`current.user` is the server-verified user, and `self.authenticated` is `True` when there is one. `current.user` is available in every channel method: `subscribed()`, your actions, and `unsubscribed()`.

This is the `AppChannel` the addon creates:

```python {title="channels/app_channel.py"}
from proper.channels import Channel
from proper.models.base import ProperModel


try:
    from ..models import Session, User
except ImportError:
    # The auth addon is not installed, so channels stay anonymous.
    Session = None


class AppChannel(Channel):
    Session = Session

    def find_user(self, user_id) -> "User | None":
        return User.get_or_none(User.id == user_id)
```

Two things make it work:

- `Session` is your app's session model. The first channel a connection subscribes to reads the session cookie, finds the session, and remembers the user's id for the whole connection. The other channels of that connection reuse it, so the cookie is read once per connection. `current.auth_session` is set only in the `subscribed()` of that first channel.
- `find_user()` loads the user by that id. It runs before every other call to the channel - each action, the `subscribed()` of the later channels, and `unsubscribed()` - so `current.user` is always fresh from the database. Change it to fit your app, for example to treat a deactivated user as no user.

Without the auth addon, `Session` is `None`, every connection is anonymous, `current.user` is `None`, and `self.authenticated` is `False`.

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

`reject()` denies the subscription: the client gets a `reject_subscription` message, the channel is discarded, and none of its actions can be called. The client never sends a stream name, only `params`; the channel checks them and picks the stream on the server. So a client cannot listen to a room it does not belong to.

---

## Actions: messages from the client

Any public method of a channel can be called by the client as an *action*:

```python
from proper import current


@router.channel()
class ChatChannel(AppChannel):
    def subscribed(self):
        self.stream_from(f"chat_{self.params['room']}")

    def speak(self, data):
        self.broadcast(
            f"chat_{self.params['room']}",
            {"message": data["message"], "sender": current.user.login},
        )

    def typing(self, data):
        self.broadcast(
            f"chat_{self.params['room']}",
            {"typing": current.user.login},
        )
```

The client calls `chat.perform("speak", {message: "hello"})` and the `speak` method runs, with the payload as `data`. An action always receives `data` (an empty dict if the client sent nothing), so every action method takes that argument.

Actions are plain synchronous Python with a database connection ready, like a controller action. The calls of one connection - its subscriptions, actions and unsubscriptions - run one at a time, in the order they arrived, in a pool of worker threads (four by default, see `workers` in [The cable server](#the-cable-server-wsecable)). A slow action keeps one of those threads busy, so move long work to a [background task](/docs/tasks) that broadcasts when it is done.

These names are refused as actions, with an `error` frame:

Refused                           | Why
--------------------------------- | ---------------------------------
Names starting with `_`           | Private methods are not actions
`subscribed`, `unsubscribed`      | Lifecycle hooks, not client-callable
`send`, `broadcast`, `reject`     | Channel internals
`stream_from`, `stop_stream_from`, `stop_all_streams` | Stream control belongs to the server
Missing or non-callable names     | There is nothing to run

Any other public method is reachable from the client, so keep helpers private with a leading `_`.

There is one conventional action name: `receive`. The client's `subscription.send(data)` is shorthand for `perform("receive", data)`, so if you define a `receive(self, data)` method it becomes the default handler for that subscription.

### Replying to the caller

`perform()` returns a promise, and what the action returns is what it resolves with. To tell the caller that something was wrong, raise `ActionError` with a reason and anything else the page needs:

```python
from proper.channels import ActionError


class ChatChannel(AppChannel):
    def speak(self, data):
        text = data.get("message", "").strip()
        if not text:
            raise ActionError("empty")
        if len(text) > 500:
            raise ActionError("too_long", max=500)
        message = Message.create(room_id=self.params["room"], text=text)
        self.broadcast(f"chat_{self.params['room']}", {"message": text})
        return {"id": message.id}
```

```javascript
try {
  const { id } = await chat.perform("speak", { message })
  input.value = ""
} catch (error) {
  showError(error.reason === "too_long" ? `At most ${error.max} characters` : "Try again")
}
```

The promise rejects with the `ActionError`'s data (`{reason: "too_long", max: 500}`), with `{reason: "error"}` when the action raised anything else (the error is logged, the client doesn't learn the details), with `{reason: "not_subscribed"}`, `{reason: "invalid_action"}` or `{reason: "unknown_action"}` when there was nothing to run, and with `{reason: "timeout"}` when no reply came in 10 seconds (`perform(action, data, {timeout})` changes that). An action that returns nothing resolves with `null`. The connection and its other subscriptions keep working after any of these.

Two things to keep in mind. A timeout means the reply didn't arrive, not that the action didn't run: the server may have finished it, and a reply that comes later is dropped, so don't retry an action that creates or sends something on a timeout without the user's say-so, or have it take an id from the client so a repeat is ignored. And you don't have to wait for the reply: `chat.perform("typing")` on its own is fine, and a rejection nobody waits for is not reported anywhere.

---

## Streams and broadcasting

Streams are the unit of delivery. A channel can stream from as many as it likes, and a broadcast to a stream reaches every channel - on every connection - that is listening to it.

Method                      | What it does
--------------------------- | -------------------------------
`.stream_from(name)`        | Start listening to a named stream
`.stop_stream_from(name)`   | Stop listening to one stream
`.stop_all_streams()`       | Stop listening to all of them
`.send(data)`               | Send to **this subscription only**
`.broadcast(name, data)`    | Send to **every subscriber** of a stream

Use `send()` to answer the one client in front of you (a confirmation, a validation error); use `broadcast()` to tell everyone listening. The data can be anything Proper can encode as JSON, including a string of HTML.

A broadcast is encoded once and every subscriber receives the same frame; it does not go through `send()`, even one you override. To tell different users different things, give them different streams, such as `f"notices_{user.id}"`.

### Naming streams

Stream names are arbitrary strings. The convention is a descriptive prefix with a dynamic suffix:

```python
self.stream_from(f"chat_{room_id}")
self.stream_from(f"inbox_{current.user.id}")
self.stream_from(f"document_{doc_id}_edits")
```

The name is the contract between the channel that listens and the code that broadcasts, and both sides have to spell it the same way. Nothing checks that they agree: a typo on one side delivers to no one, without an error. A small function that builds the name, used on both sides, avoids that:

```python
def chat_stream(room_id):
    return f"chat_{room_id}"
```

### Broadcasting from a controller or a task

The most common broadcast does not come from a channel at all - it comes from an ordinary request, or a background task, that just changed something open pages should see. Any code with the app can broadcast through `app.cable`:

```python {title="controllers/message_controller.py"}
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

A controller reaches the cable through `self.app.cable`; a background task imports the app:

```python {title="tasks/__init__.py"}
from ..main import app


@app.queue.task()
def notify_user(user_id, payload):
    app.cable.broadcast(f"inbox_{user_id}", payload)
```

The controller saves the message and redirects as usual, and the broadcast updates every open page. [Background Tasks](/docs/tasks) covers running the worker that the second example needs.

It doesn't matter which process the broadcast comes from. Only one process serves the WebSockets; a broadcast made in any other one - a task worker, a shell, the extra web processes of `PROCESSES` - is sent to it for you (see [The cable server](#the-cable-server-wsecable)).

When one request makes several broadcasts, wrap them in `app.cable.batch()`. From a process that has to send them to the cable, they then travel together, in one request instead of one each:

```python
with self.app.cable.batch():
    self.app.cable.broadcast(f"room_{room.id}", html)
    for user_id in member_ids:
        self.app.cable.broadcast(f"unreads_{user_id}", {"room_id": room.id})
```

### Closing a user's connections

A channel authorizes when it subscribes. If you take that access away later - remove someone from a room, ban them, sign them out - their open subscriptions keep receiving until they disconnect. `app.cable.disconnect(user_id=...)` closes every connection of that user, from any process. Their pages reconnect and subscribe again, and the channels that no longer authorize them reject the subscription:

```python
membership.delete_instance()
self.app.cable.disconnect(user_id=membership.user_id)
```

---

## Tracking who is connected

Channels do not have a presence API, but the lifecycle hooks are enough to build a simple one: announce in `subscribed()`, announce again in `unsubscribed()`, and let every page update its list.

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

That is enough for join and leave notices and "X is typing". Know its limits, though:

- It tells you about *events* (someone joined, someone left), not *state* (who is here right now). A page that opens later doesn't learn who was already there. For a live list of members, keep it yourself in a shared store.
- A user with three tabs joins three times. Counting each user once is up to you.
- `unsubscribed()` doesn't run if the server process dies, so a crash can leave members that never leave.

A built-in presence API that handles several tabs is one of the things Channels doesn't have yet - see [Where this could grow](#where-this-could-grow).

---

## The client: cable.js

`cable.js` is an ES module that owns the connection, your subscriptions, and reconnection. It is in the import map as `"cable"`:

```javascript
import { cable } from "cable"

cable.connect()

const chat = cable.subscribe("ChatChannel", { room: "general" }, {
  connected()    { console.log("subscribed") },
  disconnected() { console.log("connection lost") },
  rejected()     { console.log("subscription denied") },
  received(data) { addMessageToDOM(data) },
})

chat.perform("speak", { message: "hello" })  // call an action; a promise with its reply
chat.send({ message: "hello" })   // shorthand for perform("receive", data)
chat.unsubscribe()                // leave this channel
cable.disconnect()                // close the socket, stop reconnecting
```

`cable.connect()` opens the WebSocket. Calling it again while it is open, or opening, does nothing, so every script of the page can call it. With no argument, it connects to `/cable` on the current host (`ws://` on http, `wss://` on https); in development, to the port the page announces (see [The cable server](#the-cable-server-wsecable)). If you change `CABLE_PATH`, pass the full URL to `connect()`.

`cable.subscribe(channel, params, callbacks)` returns a subscription. You can subscribe before the connection is open: the subscription is sent as soon as it is. If you pass only two arguments and the second has callbacks in it, it is taken as the callbacks, with empty params.

The four callbacks are optional:

Callback         | Called when
---------------- | ------------------------------------------
`connected(info)` | The server confirmed the subscription (again after each reconnection). `info` is `{reconnected, recovered}`, see [Missed broadcasts](#missed-broadcasts-recovery)
`received(data)` | A `send()` or a broadcast arrived for this subscription
`rejected()`     | The channel called `reject()`, or no channel has that name
`disconnected()` | The connection closed, or you called `unsubscribe()`

When the connection drops, `cable.js` reconnects on its own, subscribes everything again, and gets the broadcasts it missed (see [Missed broadcasts](#missed-broadcasts-recovery)), so a short network problem is invisible to your code. A `perform()` made meanwhile waits, and is sent once the connection and its subscriptions are back; its promise still rejects with `{reason: "timeout"}` if that takes longer than its timeout, and with `{reason: "offline"}` if more than 100 calls pile up. It waits 1 second before the first attempt and twice as long before each next one, up to 30 seconds, and it never gives up. The server pings every connection every `CABLE_PING_INTERVAL` seconds; a connection that goes silent for three intervals (and at least 10 seconds) is treated as dead, closed, and opened again. This catches a laptop that went to sleep or a proxy that dropped the connection without telling anyone. `cable.disconnect()` is the only thing that stops the reconnecting.

All subscriptions share the one connection, so holding several is normal and cheap:

```javascript
const general = cable.subscribe(
    "ChatChannel", { room: "general" }, { received: render })
const random  = cable.subscribe(
    "ChatChannel", { room: "random" },  { received: render })
const inbox   = cable.subscribe(
    "InboxChannel", { received: showToast })
```

### Missed broadcasts (recovery)

The server keeps the last broadcasts of each stream: 128 by default, for 5 minutes after the last one. When a connection comes back, `cable.js` tells the server where it was in each stream, and the server sends what was broadcast since. They arrive through `received()` like any other, in order, and nothing arrives twice. The same happens when a connection falls so far behind that wse drops broadcasts for it (see [Slow clients](#slow-clients)): the broadcasts after the hole wait while the missed ones are fetched.

So `connected()` is the place to know whether the page is up to date. It gets an object:

```javascript
cable.subscribe("ChatChannel", { room: "general" }, {
  connected({ reconnected, recovered }) {
    if (reconnected && recovered === false) loadMessages()  // too much was missed
  },
  received: render,
})
```

Field         | Value
------------- | -----------------------------------------------
`reconnected` | `false` the first time, `true` after each reconnection
`recovered`   | `true` when every missed broadcast was sent; `false` when some couldn't be: the server restarted, more than the buffer holds were missed, or the stream had no history; `null` when there was nothing to ask for (the first subscription, or a stream without broadcasts before the connection dropped)

With `recovered === false`, load the state again from the server, as the page did when it first rendered. The `<turbo-stream-channel>` element does this by dispatching an event (see [Broadcasting HTML](#broadcasting-html-turbo-streams)).

What recovery does not cover: a stream that had no broadcasts before the connection dropped has no position to recover from, so what it broadcast meanwhile is lost (`recovered` is `null` for it); and `send()` messages to one subscription are not kept, only broadcasts. On the server, `recovery=False` in `CABLE` turns it off, and wse's `recovery_buffer_size`, `recovery_ttl` and `recovery_memory_budget` size the buffers (see [The cable server](#the-cable-server-wsecable)).

---

## Broadcasting HTML (Turbo Streams)

The broadcasts so far send JSON, and the `received()` callback rebuilds the DOM by hand - writing again, in JavaScript, markup you already have as a Jx component.

Proper includes [Turbo](https://turbo.hotwired.dev/), so instead you can broadcast the *rendered* component wrapped in a `<turbo-stream>` and let Turbo apply it. A live list then needs no JavaScript of your own.

A `<turbo-stream>` is HTML that names a DOM operation and a target:

```html
<turbo-stream action="append" target="messages">
  <template><li>Ana: hello</li></template>
</turbo-stream>
```

The `turbo_stream` builder has a method for each operation. Each one renders a Jx component, or takes ready-made HTML:

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

turbo_stream.update("unread_count", html="3")
turbo_stream.remove(message)                 # a model: its dom_id is the target
turbo_stream.replace(targets=".draft", html="")  # every element matching a CSS selector
```

The first argument is the id of the element to act on, or a model instance, whose `dom_id` is used. `targets=` takes a CSS selector instead, to act on every matching element. The method name is the operation:

Action               | Effect
-------------------- | ---------------------------------------------------------
`append` / `prepend` | Add the fragment as the last / first child of the target
`before` / `after`   | Insert the fragment as a sibling before / after the target
`replace`            | Swap the target element itself
`update`             | Replace the target's contents, keep the element
`remove`             | Remove the target (no fragment)
`morph`              | Update the target by morphing, keeping unchanged nodes
`refresh`            | Reload the page (takes no target)

Broadcast it like any other data:

```python {title="controllers/message_controller.py"}
from proper import current, turbo_stream

...

    def create(self):
        room_id = self.params["room_id"]
        message = Message.create(
            room_id=room_id,
            text=self.params["text"],
            author=current.user,
        )

        self.app.cable.broadcast(
            f"chat_{room_id}",
            turbo_stream.append("messages", "message.jx", message=message),
        )
        self.response.redirect_to("Message.index", room_id=room_id)
```

To subscribe a page, you don't need to write JavaScript either. Use the `<turbo-stream-channel>` element, which `cable.js` defines:

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

The element connects, subscribes to the channel with those `params`, and hands every message to Turbo, which appends the new `<li>`. When the element leaves the page, it unsubscribes. The same `Message` component renders the initial list and every live update, so the markup is defined in one place.

To subscribe from JavaScript instead, use `streamFrom`:

```javascript
import { streamFrom } from "cable"

const subscription = streamFrom("ChatChannel", { room_id: 42 })
```

Authorization doesn't change: the element sends `params`, never a stream name, and the channel's `subscribed()` still decides with `reject()` and picks the stream on the server (see [Authorizing versus authenticating](#authorizing-versus-authenticating)).

After a reconnection, the `<turbo-stream>` fragments the page missed are applied as they arrive. When they can't be recovered (see [Missed broadcasts](#missed-broadcasts-recovery)), the element dispatches a `turbo-stream-channel:gap` event, which bubbles, so the page can load the content again:

```javascript
document.addEventListener("turbo-stream-channel:gap", (event) => {
  Turbo.visit(location.href, { action: "replace" })  // or reload a frame
})
```

`streamFrom(channel, params, { onGap })` takes the same as a function.

:::note
The same fragment can also be the response of a controller, to a form submitted with Turbo. See [Turbo](/docs/turbo) for `*.turbo_stream.jx` views and the `stream` tag.
:::

---

## The cable server: Cable

The channels addon configures this cable:

```python {title="config/channels.py"}
CABLE_PATH = "/cable"
CABLE_PORT = int(os.getenv("CABLE_PORT", int(os.getenv("PORT", 2300)) + 1))
CABLE: dict = {"type": "proper.channels.Cable"}
```

`Cable` serves the WebSockets with [proper-wse](https://github.com/jpsca/proper-wse), our fork of [wse-server](https://github.com/silvermpx/wse): a WebSocket server written in Rust, with wheels for free-threaded Python, that runs inside the web process. Your channels run in Python, in its worker threads. Underneath, a stream is a wse topic, and a `broadcast()` gives wse one encoded frame, which it writes to every subscriber without going back to Python. With thousands of clients on one stream, this is what keeps up.

`proper-wse` imports as `wse_server`, so don't install the original `wse-server` next to it; `Cable` refuses to start with it.

How it runs:

- `proper run` starts the cable in its web process, before the first request, and stops it with the server. Granian serves the app over WSGI, which has no WebSockets; the cable listens on its own port, `CABLE_PORT`. Under another server, call `app.cable.start_server()` and `app.cable.stop_server()` yourself.
- Only that process serves the WebSockets. Every other process that loads the app - the extra copies of `PROCESSES`, a task worker, a shell - sends its broadcasts and `disconnect()`s to it, signed with the app's secret keys, as a `POST` to `CABLE_PATH` on `127.0.0.1`, port `CABLE_PORT + 1`. If the cable is down, the broadcast is lost and a warning is logged; the request that made it still finishes normally.
- In production, your reverse proxy routes `CABLE_PATH` to `CABLE_PORT`. [Deployment](/docs/deployment#the-reverse-proxy) shows the nginx block.
- In development there is no proxy. When `DEBUG` is on, `render_importmap()` adds a `<meta name="cable-port">` tag to the page, and `cable.js` connects to that port on the same host name.

The settings, in `config/`:

Setting                   | Default   | What it is
------------------------- | --------- | -----------------------------
`CABLE`                   | `{}`      | The cable backend: `{"type": ...}` and its options
`CABLE_PATH`              | `"/cable"`| The URL path of the WebSockets, behind the proxy
`CABLE_PORT`              | `0`       | The port of the WebSockets (the addon sets `PORT + 1`)
`CABLE_ALLOWED_ORIGINS`   | `[]`      | Other sites allowed to open a WebSocket (see [below](#checking-where-a-websocket-comes-from))
`CABLE_PING_INTERVAL`     | `3`       | Seconds between the server's pings to every connection: a whole number, at least 1, and less than the cable's `idle_timeout` (60), which closes a connection that answers no ping for that long
`CABLE_MAX_PENDING_BYTES` | 4 MB      | See "Slow clients" below. `0` is no limit
`CABLE_STALL_TIMEOUT`     | `10`      | See "Slow clients" below

And the options of `Cable`, in `CABLE`:

Option                     | Default      | What it is
-------------------------- | ------------ | -----------------------------
`port`                     | `CABLE_PORT` | Port of the WebSockets
`host`                     | `"0.0.0.0"`  | Address to listen on
`forward_port`             | `port + 1`   | Port, on 127.0.0.1, where the other processes send their broadcasts
`workers`                  | `4`          | Threads that run the channels' code
`max_connections`          | `100000`     | Connections it accepts
`max_outbound_queue_bytes` | 64 MB        | How far behind a connection can fall before wse drops broadcasts for it
`backpressure_bytes`       | 128 KB       | A `broadcast()` waits while the subscribers of its stream have more than this queued, on average. `0` never waits
`backpressure_timeout`     | `1.0`        | The longest a `broadcast()` waits, in seconds; then it is sent anyway
`recovery`                 | `True`       | Keep the last broadcasts of each stream, for clients that reconnect (see [Missed broadcasts](#missed-broadcasts-recovery))

Any other option goes to `wse_server.RustWSEServer`. For example, `max_pending_handshakes`, how many handshakes can be in progress at once; raise it if thousands of clients may reconnect together after a restart. Or the size of the recovery buffers: `recovery_buffer_size` (128 broadcasts per stream, rounded to a power of two), `recovery_ttl` (300 seconds without broadcasts before a stream's buffer is dropped) and `recovery_memory_budget` (256 MB for all of them; past it, the least used are dropped). The buffers share the bytes of the frames with the connections, so they cost memory once per broadcast, not once per subscriber.

```python {title="config/channels.py"}
CABLE = {
    "type": "proper.channels.Cable",
    "workers": 8,
    "max_pending_handshakes": 2000,
}
```

### Slow clients

A client that stops reading - a frozen tab, a very bad network - would make messages pile up in memory. Two mechanisms deal with it:

- **Backpressure.** A `broadcast()` waits, up to `backpressure_timeout`, while the subscribers of its stream are behind. Whoever broadcasts slows down to the pace of delivery, instead of every message arriving later and later. It looks at the average, so one stuck client doesn't slow everyone down.
- **Closing stuck clients.** A connection with more than `CABLE_MAX_PENDING_BYTES` waiting, that got nothing through in `CABLE_STALL_TIMEOUT` seconds, is closed; so is one with ten times that much waiting, at any speed. `cable.js` reconnects and subscribes again, and gets what it missed. Keep ten times `CABLE_MAX_PENDING_BYTES` below `max_outbound_queue_bytes`, where wse starts dropping broadcasts instead; `cable.js` notices the hole and asks for them too.

---

## Checking where a WebSocket comes from

Browsers send a site's cookies with any WebSocket to it, even one opened by a page of another site. Without a check, a malicious page could open a WebSocket to your app with your user's session. So the cable checks the `Origin` header of the handshake, and accepts:

- A handshake with no `Origin` (it doesn't come from a browser).
- One from the same host the WebSocket was opened to, or from the app's `HOST`.
- In `DEBUG`, one from `localhost` or `127.0.0.1` on the app's `PORT`.
- One listed in `CABLE_ALLOWED_ORIGINS`.

Any other is refused with a 403. To allow another site, list it:

```python {title="config/channels.py"}
CABLE_ALLOWED_ORIGINS = ["https://admin.example.com"]
```

---

## Without channels

An app without the channels addon has `CABLE = {}`: a cable that serves no WebSockets, so `broadcast()` reaches no one (it is logged at the debug level) and doesn't fail. Setting `CABLE_PORT` with an empty `CABLE` is a `ConfigError` when the app starts.

---

## Testing channels

You don't need a running server to test a channel. The test client opens a WebSocket session served from memory: it subscribes, calls actions, and disconnects, and you check the frames that come back.

These tests are `async`, so they need [pytest-asyncio](https://pytest-asyncio.readthedocs.io/):

```bash
$ uv add --dev pytest-asyncio
```

```python {title="tests/channels/test_chat_channel.py"}
import pytest


@pytest.mark.asyncio
async def test_speak_broadcasts_to_the_room(client):
    ws = client.websocket()
    task = await ws.connect()

    confirm = await ws.subscribe("ChatChannel", room="general")
    assert confirm["type"] == "confirm_subscription"

    await ws.send_action(
        "ChatChannel",
        "speak",
        {"message": "hi"},
        room="general",
    )
    msg = await ws.receive()
    assert msg["type"] == "broadcast"
    assert msg["data"] == {"message": "hi"}

    await ws.close()
    await task
```

The session's methods:

Method                                   | What it does
---------------------------------------- | ------------------------------------
`await ws.connect()`                     | Opens the connection. Returns a task that ends when the connection closes; `await` it after `close()`
`await ws.subscribe(channel, positions=None, **params)` | Subscribes, and returns the first frame the app sends back. `positions`, `{stream: {"e": ..., "o": ...}}` from the stamps of received broadcasts, asks for the ones broadcast since
`await ws.send_action(channel, action, data, **params)` | Calls an action, without asking for a reply
`await ws.perform(channel, action, data, **params)` | Calls an action and returns its reply: `{"type": "reply", "status": "ok", "data": <what it returned>}`, or `"status": "error"` with `{"reason": ...}` in `data`. Skips what the action sent before replying
`await ws.unsubscribe(channel, **params)`| Unsubscribes
`await ws.receive(timeout=1.0)`          | The next frame, parsed from JSON. Raises `TimeoutError` if nothing arrives
`await ws.close()`                       | Disconnects, which runs `unsubscribed()`
`ws.client_send(data)`, `ws.client_send_text(text)` | Sends a raw frame, to test what the app does with bad input

`subscribe()` returns the *first* frame the app sends. If `subscribed()` calls `send()`, that message comes first, and the confirmation is the next `receive()`.

Several sessions in one test share the same cable, so you can open two and check that a broadcast reaches both. A broadcast from your test code, `client.app.cable.broadcast(...)`, reaches them too.

To test an authenticated channel, sign a user in first: the handshake carries the same session cookie an HTTP request would.

```python
@pytest.mark.asyncio
async def test_anonymous_users_are_rejected(client):
    ws = client.websocket()
    await ws.connect()
    reply = await ws.subscribe("InboxChannel")
    assert reply["type"] == "reject_subscription"
    await ws.close()


@pytest.mark.asyncio
async def test_users_get_their_inbox(client, session):
    client.sign_in(session)
    ws = client.websocket()
    task = await ws.connect()
    reply = await ws.subscribe("InboxChannel")
    assert reply["type"] == "confirm_subscription"
    assert reply["streams"] == [f"inbox_{session.user_id}"]
    await ws.close()
    await task
```

The session runs the app's cable from memory (`app.cable.serve_in_memory()`): no port, no threads, and each message is handled right away. With an app whose cable serves no WebSockets (`CABLE = {}`), `connect()` raises a `RuntimeError`. The [Testing guide](/docs/testing) covers the `TestClient` and `sign_in()`.

:::note
As you can see, testing channels is one of the few places where the well-hidden `async` nature of Proper leaks into __your__ code. Sorry about that.
:::

---

## The wire protocol

`cable.js` speaks this so you don't have to, but the frames are useful to know for debugging, or for writing a client in another language. Every message is a JSON object.

The client sends three commands - `subscribe`, `message` (call an action), and `unsubscribe`:

```json
{ "command": "subscribe", "channel": "ChatChannel",
    "params": {"room": "general"},
    "positions": {"chat_general": {"e": "0000abcd", "o": 41}} }

{ "command": "message", "channel": "ChatChannel",
    "params": {"room": "general"}, "action": "speak",
    "data": {"message": "hi"}, "id": 7 }

{ "command": "unsubscribe", "channel": "ChatChannel",
    "params": {"room": "general"} }
```

The `id` of a `message` is optional: with one, the server answers with a `reply`.

The server sends back `confirm_subscription`, `reject_subscription`, `message` (from `send()`), `broadcast` (from `broadcast()`), `reply` and `error`, plus wse's own `ping`:

```json
{ "type": "confirm_subscription", "channel": "ChatChannel",
    "params": {"room": "general"}, "streams": ["chat_general"],
    "positions": {"chat_general": {"e": "0000abcd", "o": 42}},
    "recovered": true }

{ "type": "reject_subscription", "channel": "ChatChannel",
    "params": {"room": "general"} }

{ "type": "message", "channel": "ChatChannel",
    "params": {"room": "general"}, "data": {"message": "hi"} }

{ "tp": "chat_general", "e": "0000abcd", "o": 42,
    "c": "P", "type": "broadcast", "stream": "chat_general",
    "data": {"message": "hi"} }

{ "type": "reply", "id": 7, "channel": "ChatChannel",
    "params": {"room": "general"}, "status": "ok", "data": {"id": 42} }

{ "type": "reply", "id": 7, "channel": "ChatChannel",
    "params": {"room": "general"}, "status": "error",
    "data": {"reason": "too_long", "max": 500} }

{ "type": "error", "reason": "not_subscribed" }

{ "c": "WSE", "t": "ping", "p": {"server_time": "2026-10-06T12:00:00.000Z"} }
```

A broadcast is one frame, the same for every subscriber, so it can't carry each subscription's `channel` and `params`. It names the stream instead, and `confirm_subscription` lists the streams of the subscription, so the client delivers a broadcast to every subscription that streams from it. The `c` field is used by wse; ignore it.

The `tp`, `e` and `o` fields are wse's recovery stamp: the stream, the epoch of its buffer (eight hex digits; it changes when the server restarts) and the offset of the broadcast in it. A `subscribe` may carry `positions`, the last `e` and `o` the client saw per stream; the server sends again the broadcasts after them, for the streams the channel streams from, and they may arrive before the confirmation. The confirmation has the current `positions` of the streams (`null` for one without broadcasts yet) and `recovered`: `true` when everything asked for was sent again, `false` when some couldn't be, `null` when nothing was asked. Sending `subscribe` again for an existing subscription, with `positions`, also recovers. Without recovery (`recovery=False`), broadcasts carry no stamp and `recovered` is always `null`.

Subscribing again to a subscription that already exists only sends its confirmation again. A `reject_subscription` has `"reason": "unknown_channel"` when no channel has that name, and `"reason": "error"` when `subscribed()` raised an exception; a subscription your own `reject()` turned away has no reason.

A `reply` answers the `message` with the same `id`: `status: "ok"` with what the action returned as `data` (`null` if nothing), or `status: "error"` with a `reason` in `data`: the one of an `ActionError`, along with its other data; `error` when the action raised anything else; or `not_subscribed`, `invalid_action` or `unknown_action` when there was nothing to run.

A `message` without an `id` gets no reply. What would have been an error reply is an `error` frame instead, with the `reason` (and the data of an `ActionError`) at the top level; an action that raises anything else sends nothing. An `error` also reports a command the server couldn't read: `invalid_json`, `invalid_message` (JSON that is not an object), or `unknown_command`.

The `ping` is wse's, every `CABLE_PING_INTERVAL` seconds. The client answers it with `{"c": "WSE", "t": "PONG", "p": {}}`; a connection that answers none for `idle_timeout` seconds is closed. `cable.js` also uses it to tell a dead connection from a quiet one: three intervals of silence (and at least 10 seconds), and it reconnects.

---

## A full example

A room chat: an authenticated channel, a controller that saves a message and broadcasts it, and the page that ties them together.

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
```

```python {title="controllers/message_controller.py"}
from proper import current, turbo_stream

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
        self.app.cable.broadcast(
            f"chat_{room_id}",
            turbo_stream.append("messages", "message.jx", message=message),
        )
        self.response.redirect_to("Message.index", room_id=room_id)
```

```html+jinja {title="views/message/index.jx"}
{#def room, messages #}
{#import "message.jx" as Message #}

<turbo-stream-channel channel="ChatChannel" params='{"room_id": {{ room.id }}}'>
</turbo-stream-channel>

<ul id="messages">
  {% for message in messages %}
    <Message message={{ message }} />
  {% endfor %}
</ul>

<form method="post" action="{{ url_for('Message.create', room_id=room.id) }}">
  <input name="text" autocomplete="off">
  <button>Send</button>
</form>
```

The channel guards the room with the server-verified user. The controller saves the message and broadcasts it, rendered with the same component as the list. Every open page of the room, including the sender's, gets the new message, and there is no JavaScript of your own.

---

## Where this could grow

Channels covers the core - one shared connection, authenticated subscriptions, streams, broadcasting, a reconnecting client, recovery of missed broadcasts, replies to actions, and Turbo Streams. Some things that other real-time stacks offer are not here yet. None of them block you - there are workarounds - but they are where the framework will likely grow.

- **A presence API.** A real who-is-online list that handles several tabs and several machines, instead of the manual pattern shown above. The WebSocket server, wse, already keeps one: per user, across tabs, and synced between its own cluster nodes. What is missing is connecting it to Proper: wse only knows who a connection belongs to when it authenticates with a JWT, not with the session cookie, and `cable.js` doesn't understand its join and leave messages.
- **Stream names from models.** `broadcast_to(record, data)` and `stream_for(record)`, which would build the stream name from a model, so a typo can't break it silently.
- **Per-subscription timers.** A `periodically(...)` hook for server-driven updates - counters, clocks, dashboards - that lives as long as the subscription. For now, a periodic background task that broadcasts to a stream covers most of this.

If you build any of these, the framework would love a PR.

---

## What's next

Channels touches several other parts of Proper:

- [Authentication](/docs/authentication) - the session and signed cookie that `AppChannel` uses to put `current.user` on a connection.
- [Turbo](/docs/turbo) - Turbo Frames and Streams, also as responses to forms.
- [Background Tasks](/docs/tasks) - the worker behind broadcasting from a task, plus scheduling and retries.
- [Jx Components](/docs/jx_components) - the components you render into a `<turbo-stream>` to broadcast.
- [Deployment](/docs/deployment) - processes, and the cable port behind nginx.
