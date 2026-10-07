from ..channels import BaseCable
from ..errors import ConfigError
from ..helpers.imports import get_instance


NAME = "CABLE"
DEFAULT_CONFIG = {}

# Options of wse that a setting of the app decides. Given in `CABLE`, they
# would fight the setting, so they are refused.
SETTING_OF = {
    "ping_interval": "CABLE_PING_INTERVAL",
    "allowed_origins": "CABLE_ALLOWED_ORIGINS",
    "recovery_enabled": "the `recovery` option",
}


def setup(app):
    config = app.config.get(NAME, DEFAULT_CONFIG)
    if not config:
        if app.config.get("CABLE_PORT"):
            raise ConfigError(
                f"CABLE_PORT is set but {NAME} is empty, and the default cable serves no "
                f'WebSockets. Set {NAME} = {{"type": "proper.channels.Cable"}} '
                '(and `uv add proper-wse`), or remove CABLE_PORT.'
            )
        # No channels: a cable with no WebSockets, where broadcasts reach no one.
        app.cable = BaseCable()
        return

    validate_config(config)
    validate_settings(app.config, config)
    app.config[NAME] = config
    app.cable = get_instance(**config)
    # A backend that serves the WebSockets itself (Cable) needs the app,
    # to run the channels.
    if hasattr(app.cable, "bind"):
        app.cable.bind(app)


def validate_config(config):
    if not isinstance(config, dict):
        raise ConfigError(f"{NAME} config must be a dictionary")

    if "type" not in config:
        raise ConfigError(f"{NAME} config must have a 'type' key")
    if not isinstance(config["type"], (str | type)):
        raise ConfigError(f"{NAME}['type'] must be a string or a class")
    for option, setting in SETTING_OF.items():
        if option in config:
            raise ConfigError(f"{NAME}['{option}'] is set by {setting}; set that instead")
    if config.get("cluster") is not None:
        validate_cluster(config["cluster"])


def validate_cluster(cluster):
    """`CABLE['cluster']`: a `port`, then `peers` or `seeds` and `addr`,
    and `tls` with its three files or nothing."""
    where = f"{NAME}['cluster']"
    if not isinstance(cluster, dict):
        raise ConfigError(f"{where} must be a dictionary")
    unknown = set(cluster) - {"port", "peers", "seeds", "addr", "tls"}
    if unknown:
        raise ConfigError(f"{where} has unknown keys: {', '.join(sorted(unknown))}")
    _positive_int(cluster, "port", maximum=65535, where=where)
    for name in ("peers", "seeds"):
        value = cluster.get(name, [])
        if not isinstance(value, (list, tuple)) or not all(
            isinstance(v, str) and ":" in v for v in value
        ):
            raise ConfigError(f"{where}['{name}'] must be a list of 'host:port' strings")
    if not cluster.get("peers") and not cluster.get("seeds"):
        raise ConfigError(f"{where} needs 'peers' (the other machines) or 'seeds' (for gossip)")
    if cluster.get("seeds") and not isinstance(cluster.get("addr"), str):
        raise ConfigError(f"{where}['addr'], this machine's 'host:port', is needed with 'seeds'")
    tls = cluster.get("tls")
    if tls is not None and (
        not isinstance(tls, dict) or set(tls) != {"cert", "key", "ca"}
        or not all(isinstance(v, str) and v for v in tls.values())
    ):
        raise ConfigError(f"{where}['tls'] must have 'cert', 'key' and 'ca', the paths of the PEM files")


def _positive_int(config, name, *, zero_ok=False, maximum=None, where=""):
    value = config.get(name)
    if (
        not isinstance(value, int) or isinstance(value, bool)
        or value < (0 if zero_ok else 1) or (maximum is not None and value > maximum)
    ):
        at_least = "0" if zero_ok else "1"
        up_to = f" and at most {maximum}" if maximum is not None else ""
        shown = f"{where}['{name}']" if where else name
        raise ConfigError(f"{shown} must be an integer of at least {at_least}{up_to}, not {value!r}")
    return value


def validate_settings(settings, config):
    """Check the settings the cable reads (`CABLE_*`), and that they agree
    with the options in `CABLE`: the pings must come more often than wse's
    `idle_timeout` closes a quiet connection."""
    _positive_int(settings, "CABLE_PORT", zero_ok=True, maximum=65535)
    path = settings.get("CABLE_PATH")
    if not isinstance(path, str) or not path.startswith("/"):
        raise ConfigError(f"CABLE_PATH must be a path starting with '/', not {path!r}")
    interval = _positive_int(settings, "CABLE_PING_INTERVAL")
    idle_timeout = config.get("idle_timeout", 60)
    if not isinstance(idle_timeout, int) or isinstance(idle_timeout, bool) or idle_timeout <= interval:
        raise ConfigError(
            f"{NAME}['idle_timeout'] ({idle_timeout!r}) must be an integer greater than "
            f"CABLE_PING_INTERVAL ({interval}): a connection is closed when it answers no "
            "ping for that long"
        )
    _positive_int(settings, "CABLE_MAX_PENDING_BYTES", zero_ok=True)
    stall = settings.get("CABLE_STALL_TIMEOUT")
    if isinstance(stall, bool) or not isinstance(stall, (int, float)) or stall <= 0:
        raise ConfigError(f"CABLE_STALL_TIMEOUT must be a number of seconds above 0, not {stall!r}")
