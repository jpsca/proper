__all__ = ("before_action", "after_action", "around_action")


def before_action(func_or_method_name, only=None, skip=None):
    def decorator(cls):
        _filter = _build_filter(func_or_method_name, only, skip)
        _add_before_action(cls, _filter)
        return cls
    return decorator


def after_action(func_or_method_name, only=None, skip=None):
    def decorator(cls):
        _filter = _build_filter(func_or_method_name, only, skip)
        _add_after_action(cls, _filter)
        return cls
    return decorator


def around_action(func_or_method_name, only=None, skip=None):
    def decorator(cls):
        _filter = _build_filter(func_or_method_name, only, skip)
        _add_before_action(cls, _filter)
        _add_after_action(cls, _filter)
        return cls
    return decorator


def _add_before_action(cls, _filter):
    if not cls.__dict__.get("_before_action"):
        cls._before_action = (_filter, )
    else:
        cls._before_action = (_filter, ) + cls._before_action


def _add_after_action(cls, _filter):
    if not cls.__dict__.get("_after_action"):
        cls._after_action = (_filter, )
    else:
        cls._after_action = (_filter, ) + cls._after_action


def _be_a_list(something):
    if something is None:
        return []
    if isinstance(something, (list, tuple)):
        return something
    return [something]


def _build_filter(func_or_method_name, only, skip):
    _filter = {"filter": func_or_method_name}
    if only:
        _filter["only"] = _be_a_list(only)
    if skip:
        _filter["skip"] = _be_a_list(skip)
    return _filter
