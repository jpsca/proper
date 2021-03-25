import time
from threading import Thread

import pytest

from proper.local import Local


def test_basic_local():
    local = Local()
    local.foo = 0
    values = []

    def value_setter(idx):
        time.sleep(0.01 * idx)
        local.foo = idx
        time.sleep(0.02)
        values.append(local.foo)

    threads = [
        Thread(target=value_setter, args=(x,))
        for x in [1, 2, 3]
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(values) == [1, 2, 3]

    def delfoo():
        del local.foo

    delfoo()
    pytest.raises(AttributeError, lambda: local.foo)
    pytest.raises(AttributeError, delfoo)

    local.release()


def test_local_release():
    local = Local()
    local.foo = 42
    local.release()
    assert not hasattr(local, "foo")
