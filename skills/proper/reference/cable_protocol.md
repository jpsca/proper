---
title: Cable Wire Protocol
description: Reference: the JSON frames between cable.js and the cable (subscribe, message, unsubscribe; confirm, reject, broadcast, reply, error, ping)
last_verified: 2026-11-01
sources:
  - src/proper/channels
  - src/proper/_blueprints/addon_channels/assets/js/cable.js
---

# Cable Wire Protocol

Read this only to write a client other than `cable.js`, or to read frames in the browser's Network panel. Everyday use is in [channels.md](../channels.md) and [cable.md](../cable.md).

## Wire Protocol

Clients connect via WebSocket (see `cable.connect()`) and exchange JSON messages. This section documents the protocol for reference; `cable.js` handles it automatically.

### Client-to-Server Commands

**Subscribe.** `positions` is optional: the last stamp seen per stream; the server sends again the broadcasts after it, for the streams the channel streams from (they may arrive before the confirmation). Sending it for an existing subscription also recovers:

```json
{"command": "subscribe", "channel": "ChatChannel", "params": {"room": "general"}, "positions": {"chat_general": [{"e": "0000abcd", "o": 41}]}}
```

The list goes from the oldest epoch to the latest. The server reads one position per epoch (the earliest offset given) and the last `MAX_EPOCHS` (4) epochs of each stream; the rest are ignored. A stream counts as recovered when its latest epoch is: the older ones are of a buffer the server dropped and started again.

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

`presence` is `{stream: {key: data}}` for the streams the channel tracks. Presence changes arrive as frames to every subscriber of the stream, possibly before the confirmation of the subscription that caused them: `{"c": "WSE", "t": "presence_join" | "presence_leave" | "presence_update", "p": {"topic", "user_id", "data"}}`.

`positions` is where each stream is now (`null` for one with no broadcasts yet); `recovered` is `true` when every missed broadcast asked for was sent again, `false` when some couldn't be, `null` when none were asked (always `null` with `recovery=False`).

**Subscription rejected:**

```json
{"type": "reject_subscription", "channel": "ChatChannel", "params": {"room": "general"}}
```

A reject for an unregistered channel carries `"reason": "unknown_channel"`; one past the cable's `max_subscriptions` carries `"reason": "too_many_subscriptions"`; one for a `subscribed()` that raised an exception (logged, its streams stopped) carries `"reason": "error"`; a reject from your own `reject()` in `subscribed()` has no `reason`.

**Data message (from `send()`):**

```json
{"type": "message", "channel": "ChatChannel", "params": {"room": "general"}, "data": {"message": "hello"}}
```

**Broadcast (from `broadcast()`).** One frame for every subscriber, so it names the stream instead of the channel and params; clients route it to every subscription streaming from it (`confirm_subscription` lists the streams). Ignore the `c` field. `tp`/`e`/`o` are the recovery stamp (stream, epoch of its buffer, offset); absent with `recovery=False`:

```json
{"tp": "chat_general", "e": "0000abcd", "o": 42, "c": "P", "type": "broadcast", "stream": "chat_general", "data": {"message": "hello"}}
```

**Reply** to a `message` with an `id`: `status: "ok"` with what the action returned as `data` (`null` if nothing), or `status: "error"` with a `reason` in `data` (an `ActionError`'s reason and other data; `error` for any other exception; `not_subscribed`, `invalid_action` or `unknown_action` when there was nothing to run):

```json
{"type": "reply", "id": 7, "channel": "ChatChannel", "params": {"room": "general"}, "status": "ok", "data": {"id": 42}}
{"type": "reply", "id": 7, "channel": "ChatChannel", "params": {"room": "general"}, "status": "error", "data": {"reason": "too_long", "max": 500}}
```

**Error**, for a `message` without an `id` that couldn't run (its reason and an `ActionError`'s data at the top level; any other exception in the action is logged and sends `{"type": "error", "reason": "error"}`), and for a command the server couldn't read:

```json
{"type": "error", "reason": "not_subscribed"}
```

Error reasons: `invalid_json`, `unknown_command`, `invalid_message` (JSON that is not an object, or whose `channel` is not a string or `params` not an object), `not_subscribed`, `invalid_action` (empty, not a string, starting with `_`, or a blocked name), `unknown_action` (not a method your channel class defines), `error` (an exception in the action), and an `ActionError`'s reason.

**Ping**, the cable's, every `CABLE_PING_INTERVAL` seconds. The client answers `{"c":"WSE","t":"PONG","p":{}}`; one that answers none for the cable's `idle_timeout` (60 s) is closed:

```json
{"c": "WSE", "t": "ping", "p": {}}
```

A handshake from another site's page is refused with a 403 (see `CABLE_ALLOWED_ORIGINS`).
