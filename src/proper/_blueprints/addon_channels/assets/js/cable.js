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
**/
import { renderStreamMessage } from "@hotwired/turbo"

export class Subscription {
  constructor(cable, channel, params, callbacks) {
    this.cable = cable
    this.channel = channel
    this.params = params
    this.callbacks = callbacks || {}
  }

  perform(action, data) {
    this.cable._send({
      command: "message",
      channel: this.channel,
      params: this.params,
      action: action,
      data: data || {},
    })
  }

  send(data) {
    this.cable._send({
      command: "message",
      channel: this.channel,
      params: this.params,
      action: "receive",
      data: data || {},
    })
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

  _connected() {
    if (this.callbacks.connected) {
      this.callbacks.connected()
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

// The server pings every few seconds (`CABLE_PING_INTERVAL`). A connection
// that has been silent for this long is dead, even if the socket says it is
// open: a laptop that slept, a proxy that dropped it.
const STALE_AFTER = 10000
const MAX_RECONNECT_DELAY = 30000

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
    this._pinged = false
    this._monitor = null
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
      this._pinged = false
      this._startMonitor()
      for (const sub of this._pendingSubscriptions) {
        this._sendSubscribe(sub)
      }
      this._pendingSubscriptions = []
    }

    ws.onmessage = (event) => {
      this._lastSeen = Date.now()
      const msg = JSON.parse(event.data)
      if (msg.type === "ping") {
        this._pinged = true
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
      if (this._pinged && Date.now() - this._lastSeen > STALE_AFTER && this._ws) {
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
    // every subscriber, like WseCable) goes to the subscriptions streaming
    // from it, as listed in their confirmations.
    if (msg.type === "broadcast") {
      for (const sub of this._subscriptions) {
        if (sub.streams && sub.streams.has(msg.stream)) sub._receive(msg.data)
      }
      return
    }
    const sub = this._findSubscription(msg.channel, msg.params)
    if (!sub) return

    if (msg.type === "confirm_subscription") {
      sub.streams = new Set(msg.streams || [])
      sub._connected()
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
    this._send({
      command: "subscribe",
      channel: sub.channel,
      params: sub.params,
    })
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
**/

export function streamFrom(channel, params = {}) {
  cable.connect()
  return cable.subscribe(channel, params, {
    received(html) { renderStreamMessage(html) },
  })
}

class TurboCableSource extends HTMLElement {
  connectedCallback() {
    this.subscription = streamFrom(
      this.getAttribute("channel"),
      JSON.parse(this.getAttribute("params") || "{}"),
    )
  }

  disconnectedCallback() {
    if (this.subscription) {
      this.subscription.unsubscribe()
    }
  }
}

customElements.define("turbo-stream-channel", TurboCableSource)
