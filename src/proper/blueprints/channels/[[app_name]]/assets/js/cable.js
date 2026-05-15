/**
WebSocket client for Proper channels.
Copyright (c) JPScaletti, MIT License

Usage:

```
import { cable } from "/cable.js"

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

class Subscription {
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

  Private

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


class Cable {
  constructor() {
    this._ws = null
    this._url = null
    this._subscriptions = []
    this._pendingSubscriptions = []
    this._reconnectAttempts = 0
    this._maxReconnectAttempts = 10
    this._reconnectDelay = 1000
    this._shouldReconnect = true
  }

  connect(url) {
    if (!url) {
      const protocol = location.protocol === "https:" ? "wss:" : "ws:"
      url = `${protocol}//${location.host}/cable`
    }
    this._url = url
    this._shouldReconnect = true
    this._open()
  }

  disconnect() {
    this._shouldReconnect = false
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

  Private

  _open() {
    this._ws = new WebSocket(this._url)

    this._ws.onopen = () => {
      this._reconnectAttempts = 0
      for (const sub of this._pendingSubscriptions) {
        this._sendSubscribe(sub)
      }
      this._pendingSubscriptions = []
    }

    this._ws.onmessage = (event) => {
      const msg = JSON.parse(event.data)
      this._dispatch(msg)
    }

    this._ws.onclose = () => {
      for (const sub of this._subscriptions) {
        sub._disconnected()
      }
      if (this._shouldReconnect) {
        this._reconnect()
      }
    }
  }

  _reconnect() {
    if (this._reconnectAttempts >= this._maxReconnectAttempts) {
      return
    }
    this._reconnectAttempts++
    const delay = this._reconnectDelay * Math.pow(2, this._reconnectAttempts - 1)
    setTimeout(() => {
      this._pendingSubscriptions = [...this._subscriptions]
      this._open()
    }, delay)
  }

  _dispatch(msg) {
    const sub = this._findSubscription(msg.channel, msg.params)
    if (!sub) return

    if (msg.type === "confirm_subscription") {
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
export { Cable, Subscription }
