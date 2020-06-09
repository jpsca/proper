from proper.support import be_a_list


__all__ = ("before_action", "after_action", "around_action")


def before_action(func_or_method_name, only=None, skip=None):
    def decorator(cls):
        _filter = _build_filter(func_or_method_name, only, skip)
        cls._before_action = (_filter, ) + cls._before_action
        return cls
    return decorator


def after_action(func_or_method_name, only=None, skip=None):
    def decorator(cls):
        _filter = _build_filter(func_or_method_name, only, skip)
        cls._after_action = (_filter, ) + cls._after_action
        return cls
    return decorator


def around_action(func_or_method_name, only=None, skip=None):
    def decorator(cls):
        _filter = _build_filter(func_or_method_name, only, skip)
        cls._before_action = (_filter, ) + cls._before_action
        cls._after_action = (_filter, ) + cls._after_action
        return cls
    return decorator


def _build_filter(func_or_method_name, only, skip):
    _filter = {"filter": func_or_method_name}
    if only:
        _filter["only"] = be_a_list(only)
    if skip:
        _filter["skip"] = be_a_list(skip)
    return _filter
