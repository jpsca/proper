/**
WebSocket client for Proper channels.

Usage:

```
import { cable } from "cable"

cable.connect()

const chat = cable.subscribe("ChatChannel", { room: "general" }, {
  connected()    { console.log("connected") },
  disconnected() { console.log("disconnected") },
  received(data) { console.log(data) },
})

chat.perform("speak", { message: "hello" })
chat.unsubscribe()
```

`perform()` returns a promise with the action's reply: it resolves with what
the action returned, and rejects with `{reason, ...}` when the action raised
an `ActionError`, failed, wasn't found, or didn't answer in time:

```
try {
  const { id } = await chat.perform("speak", { message: "hello" })
} catch (error) {
  if (error.reason === "too_long") ...
}
```

A `perform()` made while the connection is down waits in a queue and is sent
once the connection, and its subscriptions, are back.

A timeout means the reply didn't come, not that the action didn't run: a
reply that arrives later is dropped. Retrying can run the action twice.

The server keeps the last broadcasts of each stream. After a reconnection,
or a gap in what it received, the cable asks for the ones it missed, and
they arrive through `received()` as if nothing had happened. `connected()`
gets `{reconnected, recovered}`: `recovered` is `false` when some couldn't
be recovered (the server restarted, or too many were missed), the moment to
load the state again:

```
connected({ reconnected, recovered }) {
  if (reconnected && recovered === false) reloadMessages()
}
```
**/
import { renderStreamMessage } from "@hotwired/turbo"

export class Subscription {
  constructor(cable, channel, params, callbacks) {
    this.cable = cable
    this.channel = channel
    this.params = params
    this.callbacks = callbacks || {}
  }

  perform(action, data, { timeout = REPLY_TIMEOUT } = {}) {
    return this.cable._perform({
      command: "message",
      channel: this.channel,
      params: this.params,
      action: action,
      data: data || {},
    }, timeout)
  }

  send(data, options) {
    return this.perform("receive", data, options)
  }

  unsubscribe() {
    this.cable._send({
      command: "unsubscribe",
      channel: this.channel,
      params: this.params,
    })
    this.cable._removeSubscription(this)
    if (this.callbacks.disconnected) {
      this.callbacks.disconnected()
    }
  }

  // Private

  _receive(data) {
    if (this.callbacks.received) {
      this.callbacks.received(data)
    }
  }

  _connected(info) {
    if (this.callbacks.connected) {
      this.callbacks.connected(info)
    }
  }

  _disconnected() {
    if (this.callbacks.disconnected) {
      this.callbacks.disconnected()
    }
  }

  _rejected() {
    if (this.callbacks.rejected) {
      this.callbacks.rejected()
    }
  }
}

// The server pings every `CABLE_PING_INTERVAL` seconds. A connection that
// has been silent for three intervals (and at least this long) is dead, even
// if the socket says it is open: a laptop that slept, a proxy that dropped it.
const STALE_AFTER = 10000
const MAX_RECONNECT_DELAY = 30000
const WSE_PONG = '{"c":"WSE","t":"PONG","p":{}}'
// How long `perform()` waits for its reply, in milliseconds.
const REPLY_TIMEOUT = 10000
// How many `perform()`s wait for the connection to come back. Past it, the
// oldest is rejected with `{reason: "offline"}`.
const MAX_QUEUED = 100
// How long the broadcasts after a gap in a stream wait for the missed ones
// to be sent again, before being delivered anyway.
const GAP_TIMEOUT = 5000

export class Cable {
  constructor() {
    this._ws = null
    this._url = null
    this._subscriptions = []
    this._pendingSubscriptions = []
    this._reconnectAttempts = 0
    this._reconnectDelay = 1000
    this._reconnectTimer = null
    this._shouldReconnect = true
    this._lastSeen = 0
    this._lastPing = 0
    this._staleAfter = STALE_AFTER
    this._monitor = null
    this._nextId = 1
    this._replies = new Map()  // id -> {resolve, reject, timer}
    this._queued = []  // commands waiting for the connection
    // Where this connection is in each stream, from the stamps of the
    // broadcasts (`e`, the epoch of the stream's buffer in the server, and
    // `o`, the offset of the message in it). Sent with each subscribe, so
    // the server can send what was missed.
    this._positions = new Map()  // stream -> {e, o}
    // The broadcasts that arrived after a gap, held until the missed ones
    // fill it, so they are delivered in order.
    this._held = new Map()  // stream -> {frames: Map<o, msg>, timer}
  }

  connect(url) {
    // One socket for every subscription of the page: calling this again
    // while connected, or connecting, does nothing.
    if (this._ws && this._ws.readyState <= WebSocket.OPEN) return
    if (!url) {
      const protocol = location.protocol === "https:" ? "wss:" : "ws:"
      // In development the cable runs on its own port, announced by the page.
      const port = document.querySelector('meta[name="cable-port"]')?.content
      const host = port ? `${location.hostname}:${port}` : location.host
      url = `${protocol}//${host}/cable`
    }
    this._url = url
    this._shouldReconnect = true
    this._open()
  }

  disconnect() {
    this._shouldReconnect = false
    clearTimeout(this._reconnectTimer)
    this._stopMonitor()
    if (this._ws) {
      this._ws.close()
    }
  }

  subscribe(channel, params, callbacks) {
    if (typeof params === "object" && !callbacks && (params.connected || params.disconnected || params.received || params.rejected)) {
      callbacks = params
      params = {}
    }
    params = params || {}
    callbacks = callbacks || {}

    const subscription = new Subscription(this, channel, params, callbacks)
    this._subscriptions.push(subscription)

    if (this._isOpen()) {
      this._sendSubscribe(subscription)
    } else {
      this._pendingSubscriptions.push(subscription)
    }

    return subscription
  }

  // Private

  _open() {
    const ws = this._ws = new WebSocket(this._url)

    ws.onopen = () => {
      this._reconnectAttempts = 0
      this._lastSeen = Date.now()
      this._lastPing = 0
      this._startMonitor()
      for (const sub of this._pendingSubscriptions) {
        this._sendSubscribe(sub)
      }
      this._pendingSubscriptions = []
      // After the subscriptions: the server runs the commands of a
      // connection in order, so the subscriptions exist by then.
      const queued = this._queued
      this._queued = []
      for (const msg of queued) this._send(msg)
    }

    ws.onmessage = (event) => {
      this._lastSeen = Date.now()
      const msg = JSON.parse(event.data)
      if (msg.c === "WSE") {
        // The server's ping. It closes a connection that answers none for
        // `idle_timeout`, so a page that only listens answers it. The time
        // between two of them says how long a silence is too long.
        if (msg.t === "ping") {
          ws.send(WSE_PONG)
          const now = Date.now()
          if (this._lastPing) this._staleAfter = Math.max(STALE_AFTER, 3 * (now - this._lastPing))
          this._lastPing = now
        }
        return
      }
      this._dispatch(msg)
    }

    ws.onclose = () => {
      // A socket replaced by a newer one is no longer this cable's.
      if (ws !== this._ws) return
      this._stopMonitor()
      for (const sub of this._subscriptions) {
        sub._disconnected()
      }
      if (this._shouldReconnect) {
        this._reconnect()
      }
    }
  }

  _reconnect() {
    this._reconnectAttempts++
    const delay = Math.min(
      this._reconnectDelay * Math.pow(2, this._reconnectAttempts - 1),
      MAX_RECONNECT_DELAY,
    ) * (0.8 + Math.random() * 0.4)
    clearTimeout(this._reconnectTimer)
    this._reconnectTimer = setTimeout(() => {
      this._pendingSubscriptions = [...this._subscriptions]
      this._open()
    }, delay)
  }

  _startMonitor() {
    this._stopMonitor()
    this._monitor = setInterval(() => {
      // Only once the server has shown it pings: one that does not would
      // have every quiet connection taken for dead.
      if (this._lastPing && Date.now() - this._lastSeen > this._staleAfter && this._ws) {
        // Silent for too long: drop it and open a new one.
        this._ws.close()
      }
    }, STALE_AFTER / 2)
  }

  _stopMonitor() {
    clearInterval(this._monitor)
    this._monitor = null
  }

  _dispatch(msg) {
    // A broadcast that names its stream (a cable that writes one frame for
    // every subscriber, like Cable) goes to the subscriptions streaming
    // from it, as listed in their confirmations.
    if (msg.type === "broadcast") {
      if (msg.e !== undefined) this._advance(msg)
      else this._deliver(msg)
      return
    }
    if (msg.type === "reply") {
      this._settle(msg.id, msg.status === "ok", msg.data)
      return
    }
    if (msg.type === "error") {
      // A command without an id, or one the server couldn't read.
      console.warn("[cable] error:", msg.reason)
      return
    }
    const sub = this._findSubscription(msg.channel, msg.params)
    if (!sub) return

    if (msg.type === "confirm_subscription") {
      sub.streams = new Set(msg.streams || [])
      for (const [stream, pos] of Object.entries(msg.positions || {})) {
        // Where the stream is now: taken when this connection has no
        // position yet, or its own was useless (the server restarted, or
        // the stream's history is gone); the missed broadcasts, if they
        // could be sent, bring their own stamps.
        // The missed ones can't be sent again: what waited for them goes out
        if (msg.recovered === false) this._release(stream)
        if (pos && (!this._positions.has(stream) || msg.recovered === false)) {
          this._positions.set(stream, pos)
        }
      }
      const reconnected = sub.confirmed === true
      sub.confirmed = true
      sub._connected({ reconnected, recovered: msg.recovered ?? null })
    } else if (msg.type === "reject_subscription") {
      sub._rejected()
      this._removeSubscription(sub)
    } else if (msg.type === "message") {
      sub._receive(msg.data)
    }
  }

  _findSubscription(channel, params) {
    const paramsKey = JSON.stringify(params || {})
    return this._subscriptions.find(
      (sub) => sub.channel === channel && JSON.stringify(sub.params) === paramsKey
    )
  }

  _removeSubscription(sub) {
    const index = this._subscriptions.indexOf(sub)
    if (index !== -1) {
      this._subscriptions.splice(index, 1)
    }
  }

  _sendSubscribe(sub) {
    const msg = { command: "subscribe", channel: sub.channel, params: sub.params }
    // Where this connection was in the streams it had: the server sends
    // what was broadcast since, for the ones the channel streams from again.
    const positions = {}
    let any = false
    for (const stream of sub.streams || []) {
      const pos = this._positions.get(stream)
      if (pos) { positions[stream] = pos; any = true }
    }
    if (any) msg.positions = positions
    this._send(msg)
  }

  _deliver(msg) {
    for (const sub of this._subscriptions) {
      if (sub.streams && sub.streams.has(msg.stream)) sub._receive(msg.data)
    }
  }

  // A stamped broadcast arrived. One already seen (sent again by a
  // recovery) is dropped. One that leaves a gap means some were lost (the
  // server dropped them for a slow connection): it waits, and the
  // subscriptions of the stream subscribe again, with their position, to
  // get the missed ones; those fill the gap and the held ones follow.
  _advance(msg) {
    const { stream, e, o } = msg
    const pos = this._positions.get(stream)
    if (pos && pos.e === e) {
      if (o <= pos.o) return
      if (o > pos.o + 1) {
        this._hold(msg)
        return
      }
    }
    this._positions.set(stream, { e, o })
    this._deliver(msg)
    const held = this._held.get(stream)
    if (held) {
      let next
      while ((next = held.frames.get(this._positions.get(stream).o + 1))) {
        held.frames.delete(next.o)
        this._positions.set(stream, { e: next.e, o: next.o })
        this._deliver(next)
      }
      if (held.frames.size === 0) this._release(stream)
    }
  }

  _hold(msg) {
    let held = this._held.get(msg.stream)
    if (!held) {
      held = { frames: new Map(), timer: setTimeout(() => this._release(msg.stream), GAP_TIMEOUT) }
      this._held.set(msg.stream, held)
      for (const sub of this._subscriptions) {
        if (sub.streams && sub.streams.has(msg.stream)) this._sendSubscribe(sub)
      }
    }
    held.frames.set(msg.o, msg)
  }

  // Deliver what waited for a gap, in order, filled or not.
  _release(stream) {
    const held = this._held.get(stream)
    if (!held) return
    clearTimeout(held.timer)
    this._held.delete(stream)
    const frames = [...held.frames.values()].sort((a, b) => a.o - b.o)
    for (const msg of frames) {
      const pos = this._positions.get(stream)
      if (pos && pos.e === msg.e && msg.o <= pos.o) continue
      this._positions.set(stream, { e: msg.e, o: msg.o })
      this._deliver(msg)
    }
  }

  _perform(msg, timeout) {
    const id = msg.id = this._nextId++
    const reply = new Promise((resolve, reject) => {
      const timer = setTimeout(() => this._settle(id, false, { reason: "timeout" }), timeout)
      this._replies.set(id, { resolve, reject, timer })
      if (this._isOpen()) {
        this._send(msg)
      } else {
        if (this._queued.length >= MAX_QUEUED) {
          this._settle(this._queued.shift().id, false, { reason: "offline" })
        }
        this._queued.push(msg)
      }
    })
    // A caller that doesn't wait for the reply (`chat.perform("typing")`)
    // must not get an "unhandled rejection" when it fails; one that does
    // still gets the rejection.
    reply.catch(() => {})
    return reply
  }

  _settle(id, ok, data) {
    const reply = this._replies.get(id)
    if (!reply) return  // already settled: a late reply after its timeout
    this._replies.delete(id)
    clearTimeout(reply.timer)
    this._queued = this._queued.filter((msg) => msg.id !== id)
    if (ok) reply.resolve(data)
    else reply.reject(data)
  }

  _send(msg) {
    if (this._isOpen()) {
      this._ws.send(JSON.stringify(msg))
    }
  }

  _isOpen() {
    return this._ws && this._ws.readyState === WebSocket.OPEN
  }
}

export const cable = new Cable()


/**
Bridge Proper channels to Turbo Streams.

The server broadcasts `<turbo-stream>` HTML over a channel; this hands every
incoming frame to Turbo's stream renderer, which applies it to the DOM. You
write no DOM code: Turbo already implements append, prepend, replace, update,
remove, before, after and morph.

Subscribe declaratively from a view, no JavaScript required:

```
<turbo-stream-channel channel="ChatChannel" params='{"room_id": 42}'>
</turbo-stream-channel>
```

Or imperatively:

```
import { streamFrom } from "cable"
const sub = streamFrom("ChatChannel", { room_id: 42 })
```

Broadcasts missed during a reconnection are applied on return. When they
can't be (the server restarted, or too many were missed), the element
dispatches `turbo-stream-channel:gap`, which bubbles: listen to it to load
the content again, for example with `Turbo.visit(location.href)` or by
reloading a frame. `streamFrom()` takes the same as `onGap`.
**/

export function streamFrom(channel, params = {}, { onGap } = {}) {
  cable.connect()
  return cable.subscribe(channel, params, {
    received(html) { renderStreamMessage(html) },
    connected({ reconnected, recovered }) {
      if (reconnected && recovered === false && onGap) onGap()
    },
  })
}

class TurboCableSource extends HTMLElement {
  connectedCallback() {
    this.subscription = streamFrom(
      this.getAttribute("channel"),
      JSON.parse(this.getAttribute("params") || "{}"),
      {
        onGap: () => this.dispatchEvent(
          new CustomEvent("turbo-stream-channel:gap", { bubbles: true })
        ),
      },
    )
  }

  disconnectedCallback() {
    if (this.subscription) {
      this.subscription.unsubscribe()
    }
  }
}

customElements.define("turbo-stream-channel", TurboCableSource)
