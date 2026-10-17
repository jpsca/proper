"""`Cable` on several machines, through Redis.

```python
CABLE = {
    "type": "proper.channels.RedisCable",
    "url": "redis://localhost:6379/0",
    "prefix": "myapp:cable:",
}
```

Each machine's web process serves its own WebSockets, as `Cable` does. A broadcast goes straight to the subscribers of the process
that makes it, if it serves any, and to Redis, where the web processes of the
other machines get it and hand it to theirs. Each skips what it published
itself. A process without WebSockets (a task worker, a shell) only publishes
to Redis, so there is no forwarding over HTTP. `disconnect()` goes the same
way.

Redis pub/sub carries events, not state: a process that is reconnecting to
Redis misses what was published meanwhile. Recovery works on the machine a
client was on: each machine stamps the broadcasts it delivers with its own
epoch. Tests that run the cable from memory (`TestClient.websocket()`) don't
use Redis.

Presence is one list for all the machines, kept in Redis: a hash per
stream, `user -> {machine: [data, connections, time]}`, changed with a Lua
script, so that only the first connection of a user anywhere is a join, and
only the last one a leave. Each machine refreshes a key with a TTL; when one
stops refreshing it (it died), another drops what it had there and tells the
subscribers who left. Without Redis, each machine lists only its own.
"""
import threading
import time
import typing as t
import uuid

from ..helpers import jsonplus, logger
from .cable import Cable, InMemoryServer, _broadcast_frame


if t.TYPE_CHECKING:
    from ..app import App


# Imported on first use: an app with another cable should not pay for loading
# the library at startup.
redis: t.Any = None

# Longest the listener waits between attempts to reconnect.
MAX_RECONNECT_DELAY = 30
# Seconds without a message before the listener PINGs Redis
HEALTH_CHECK_INTERVAL = 30
# How long `start_server()` waits for the listener to subscribe.
SUBSCRIBE_WAIT = 1.0
# Every how many seconds a machine says it is alive, and how long that lasts:
# a machine silent for longer has its presence dropped by another.
ALIVE_EVERY = 5.0
ALIVE_TTL = 15

# A user's entry for one machine in a stream's presence hash, set (ARGV[3],
# JSON text, kept as text) or removed (ARGV[3] empty). The user's value maps
# each machine to its entry. 1: the user is present now and wasn't; -1: was,
# and no longer is; 0: neither.
_SET_PRESENCE = """
local value = redis.call('HGET', KEYS[1], ARGV[1])
local machines = value and cjson.decode(value) or {}
local before = next(machines) ~= nil
if ARGV[3] == '' then machines[ARGV[2]] = nil else machines[ARGV[2]] = ARGV[3] end
local after = next(machines) ~= nil
if after then
  redis.call('HSET', KEYS[1], ARGV[1], cjson.encode(machines))
else
  redis.call('HDEL', KEYS[1], ARGV[1])
end
if before == after then return 0 elseif after then return 1 else return -1 end
"""
# A machine's entries out of a stream's presence hash (ARGV[1]). Returns the
# users no longer present anywhere, each followed by the entry it had.
_DROP_MACHINE = """
local gone = {}
local all = redis.call('HGETALL', KEYS[1])
for i = 1, #all, 2 do
  local machines = cjson.decode(all[i + 1])
  local entry = machines[ARGV[1]]
  if entry then
    machines[ARGV[1]] = nil
    if next(machines) == nil then
      redis.call('HDEL', KEYS[1], all[i])
      table.insert(gone, all[i])
      table.insert(gone, entry)
    else
      redis.call('HSET', KEYS[1], all[i], cjson.encode(machines))
    end
  end
end
return gone
"""


def _load_redis() -> None:
    global redis
    if redis is not None:
        return
    try:
        import redis as module
    except ImportError:
        raise ImportError(
            "redis is required to use RedisCable. Install it with: uv add redis"
        ) from None
    redis = module


class RedisCable(Cable):
    """See the module. Takes the options of `Cable` too."""

    # The other processes publish to Redis instead of forwarding over HTTP.
    takes_forwarded = False

    def __init__(
        self,
        url: str = "redis://localhost:6379/0",
        prefix: str = "proper:cable:",
        **options: t.Any,
    ) -> None:
        _load_redis()
        super().__init__(**options)
        self._url = url
        self._prefix = prefix
        self._channel = prefix + "broadcasts"
        # Tells this process's own messages apart when they come back.
        self._origin = uuid.uuid4().hex
        self._publisher: t.Any = None
        self._publisher_lock = threading.Lock()
        self._listener: threading.Thread | None = None
        self._listening = threading.Event()  # cleared to stop the listener
        self._subscribed = threading.Event()
        self._scripts: dict[str, t.Any] = {}
        self._beater: threading.Thread | None = None
        self._beating = threading.Event()  # cleared to stop the heartbeat

    def bind(self, app: "App") -> None:
        self.app = app  # nothing to forward to

    # Broadcasting

    def broadcast(self, stream_name: str, data: t.Any) -> None:
        frame = _broadcast_frame(stream_name, data)
        if self.serving:
            self._send_frame(stream_name, frame)
            if isinstance(self.server, InMemoryServer):
                return  # a test: no other machines
        self._publish({"o": self._origin, "s": stream_name, "f": frame})

    def disconnect(self, *, user_id: t.Any) -> None:
        who = {"user_id": user_id}
        if self.serving:
            self._disconnect_local(who)
            if isinstance(self.server, InMemoryServer):
                return
        self._publish({"o": self._origin, "x": who})

    def _publish(self, message: dict) -> None:
        """Publish to the other machines. A Redis that is down loses the
        message and logs it; the page that broadcast still renders."""
        try:
            self._get_publisher().publish(self._channel, jsonplus.dumps(message))
        except redis.RedisError as error:
            logger.warning("⚠️ [cable] could not publish to Redis at %s: %s", self._url, error)

    def _get_publisher(self) -> t.Any:
        # Broadcasts come from any thread: one client, with its own pool.
        with self._publisher_lock:
            if self._publisher is None:
                self._publisher = redis.from_url(self._url)
            return self._publisher

    # Lifecycle

    def start_server(self) -> None:
        """Serve this machine's WebSockets, and deliver what the other
        machines publish. Waits a moment for the subscription, so that what is
        published right after the start isn't missed."""
        super().start_server()
        with self._start_lock:
            if self._listener is not None:
                return
            self._listening.set()
            self._subscribed.clear()
            self._listener = threading.Thread(
                target=self._listen, name="proper-cable-redis", daemon=True
            )
            self._listener.start()
            if self._presence:  # alive before the first connection
                self._beat()
                self._beating.set()
                self._beater = threading.Thread(
                    target=self._keep_beating, name="proper-cable-alive", daemon=True
                )
                self._beater.start()
        if not self._subscribed.wait(SUBSCRIBE_WAIT):
            logger.warning(
                "⚠️ [cable] not subscribed to Redis at %s yet: broadcasts from "
                "other machines arrive once it is", self._url,
            )

    def stop_server(self) -> None:
        beater = self._beater
        if beater is not None:
            self._beating.clear()
            beater.join()
            self._beater = None
        listener = self._listener
        if listener is not None:
            self._listening.clear()
            listener.join()
            self._listener = None
        shared = self._shares_presence()
        super().stop_server()  # the connections leave, in Redis too
        if shared:
            self._leave_redis()
        with self._publisher_lock:
            if self._publisher is not None:
                self._publisher.close()
                self._publisher = None
            self._scripts.clear()

    # Presence, one list for all the machines

    def _shares_presence(self) -> bool:
        """Whether presence goes through Redis: serving on a port, with
        presence on. A test's cable, from memory, keeps it local."""
        return self.serving and self._presence and not isinstance(self.server, InMemoryServer)

    def _presence_key(self, stream_name: str) -> str:
        return f"{self._prefix}presence:{stream_name}"

    def _streams_key(self, origin: str) -> str:
        """The streams a machine has entries in, to drop them when it dies."""
        return f"{self._prefix}presence-streams:{origin}"

    def _alive_key(self, origin: str) -> str:
        return f"{self._prefix}alive:{origin}"

    def _script(self, name: str, source: str) -> t.Any:
        client = self._get_publisher()
        with self._publisher_lock:
            if name not in self._scripts:
                self._scripts[name] = client.register_script(source)
            return self._scripts[name]

    def _presence_changed(
        self, kind: str, stream_name: str, user: str, data: t.Any, connections: int
    ) -> None:
        """This machine's entry for the user in Redis first; the subscribers
        of every machine hear of a join or a leave only when it is the user's
        first or last connection anywhere."""
        if not self._shares_presence():
            super()._presence_changed(kind, stream_name, user, data, connections)
            return
        entry = "" if kind == "leave" else jsonplus.dumps([data, connections, time.time()])
        try:
            if entry:
                self._get_publisher().sadd(self._streams_key(self._origin), stream_name)
            change = self._script("set", _SET_PRESENCE)(
                keys=[self._presence_key(stream_name)], args=[user, self._origin, entry]
            )
        except redis.RedisError as error:
            logger.warning(
                "⚠️ [cable] could not share presence through Redis at %s: %s", self._url, error
            )
            super()._presence_changed(kind, stream_name, user, data, connections)
            return
        if (
            (kind == "join" and change == 1) or (kind == "leave" and change == -1)
            or kind == "update"
        ):
            self._presence_event(f"presence_{kind}", stream_name, user, data)

    def _presence_event(self, kind: str, stream_name: str, user: str, data: t.Any) -> None:
        """A presence event for the subscribers of every machine."""
        self._presence_local(kind, stream_name, user, data)
        self._publish({"o": self._origin, "p": [kind, stream_name, user, data]})

    def _presence_local(self, kind: str, stream_name: str, user: str, data: t.Any) -> None:
        if self.serving:
            self.server._presence_frame(kind, stream_name, user, data)

    def presence(self, stream_name: str) -> dict[str, dict]:
        """Who is in the stream on every machine. A user's data is the one
        set last; `connections` counts theirs on all the machines."""
        if not self._shares_presence():
            return super().presence(stream_name)
        try:
            values = self._get_publisher().hgetall(self._presence_key(stream_name))
        except redis.RedisError as error:
            logger.warning(
                "⚠️ [cable] could not read presence from Redis at %s: %s", self._url, error
            )
            return super().presence(stream_name)
        present = {}
        for user, machines in values.items():
            entries = [jsonplus.loads(entry) for entry in jsonplus.loads(machines).values()]
            present[user.decode()] = {
                "data": max(entries, key=lambda entry: entry[2])[0],
                "connections": sum(entry[1] for entry in entries),
            }
        return present

    def _beat(self) -> None:
        """Say this machine is alive, and drop the presence of the machines
        that stopped saying so (one machine drops each: the first to get
        its `purging` key)."""
        try:
            client = self._get_publisher()
            client.set(self._alive_key(self._origin), "1", ex=ALIVE_TTL)
            client.sadd(f"{self._prefix}machines", self._origin)
            for member in client.smembers(f"{self._prefix}machines"):
                origin = member.decode()
                if origin == self._origin or client.exists(self._alive_key(origin)):
                    continue
                if client.set(f"{self._prefix}purging:{origin}", "1", nx=True, ex=ALIVE_TTL):
                    self._drop_machine(origin)
        except redis.RedisError as error:
            logger.warning(
                "⚠️ [cable] could not keep presence in Redis at %s: %s", self._url, error
            )

    def _keep_beating(self) -> None:
        while self._beating.is_set():
            self._beat()
            deadline = time.monotonic() + ALIVE_EVERY
            while self._beating.is_set() and time.monotonic() < deadline:
                time.sleep(0.05)

    def _drop_machine(self, origin: str) -> None:
        """A machine's entries out of the presence lists; its users present
        nowhere else leave."""
        client = self._get_publisher()
        streams_key = self._streams_key(origin)
        for member in client.smembers(streams_key):
            stream_name = member.decode()
            gone = self._script("drop", _DROP_MACHINE)(
                keys=[self._presence_key(stream_name)], args=[origin]
            )
            for user, entry in zip(gone[::2], gone[1::2], strict=True):
                self._presence_event(
                    "presence_leave", stream_name, user.decode(), jsonplus.loads(entry)[0]
                )
        client.delete(streams_key)
        client.srem(f"{self._prefix}machines", origin)

    def _leave_redis(self) -> None:
        """This machine stops: what it still has in Redis goes."""
        try:
            self._drop_machine(self._origin)
            self._get_publisher().delete(self._alive_key(self._origin))
        except redis.RedisError as error:
            logger.warning(
                "⚠️ [cable] could not take this machine's presence out of Redis at %s: %s",
                self._url, error,
            )

    def _listen(self) -> None:
        """Subscribe to Redis and deliver what the other machines publish.

        Reconnects whenever the subscription ends. One that outlives its own
        backoff counts as healthy and resets the wait; one that dies sooner is
        flapping, so each retry waits twice as long as the last.
        """
        delay = 0
        while self._listening.is_set():
            started = time.monotonic()
            # Neither connects yet: subscribing does. While no message comes,
            # a PING every `HEALTH_CHECK_INTERVAL` seconds finds a connection
            # that died without closing (a NAT that forgot it, a failover).
            client = redis.from_url(
                self._url, health_check_interval=HEALTH_CHECK_INTERVAL, socket_keepalive=True
            )
            pubsub = client.pubsub(ignore_subscribe_messages=True)
            try:
                pubsub.subscribe(self._channel)
                self._subscribed.set()
                while self._listening.is_set():
                    message = pubsub.get_message(timeout=0.2)
                    if message is not None:
                        try:
                            self._receive(message["data"])
                        except Exception:
                            # One bad message, not a lost connection
                            logger.exception("⚠️ [cable] could not deliver a message from Redis")
                return
            except Exception as error:
                reason = error
            finally:
                self._subscribed.clear()
                for closable in (pubsub, client):
                    try:
                        closable.close()
                    except Exception:  # pragma: no cover - closing a dead connection
                        pass
            lasted = time.monotonic() - started
            delay = 1 if lasted >= delay else min(delay * 2, MAX_RECONNECT_DELAY)
            logger.warning(
                "⚠️ [cable] Redis connection lost (%s), reconnecting in %ds", reason, delay,
            )
            deadline = time.monotonic() + delay
            while self._listening.is_set() and time.monotonic() < deadline:
                time.sleep(0.05)

    def _receive(self, raw: bytes | str) -> None:
        try:
            message = jsonplus.loads(raw)
        except ValueError:
            logger.warning("⚠️ [cable] ignored a message in Redis that isn't JSON")
            return
        if not isinstance(message, dict):
            logger.warning("⚠️ [cable] ignored a message in Redis that isn't an object")
            return
        if message.get("o") == self._origin:
            return  # ours, already delivered here
        if "f" in message:
            self._send_frame(message["s"], message["f"])
        elif "x" in message:
            self._disconnect_local(message["x"])
        elif "p" in message:
            self._presence_local(*message["p"])
