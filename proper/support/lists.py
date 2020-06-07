__all__ = ("be_a_list", )


def be_a_list(something):
    if something is None:
        return []
    if isinstance(something, (list, tuple)):
        return something
    return [something]
