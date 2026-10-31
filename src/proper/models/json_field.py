import peewee as pw

from ..helpers import jsonplus


class JSONField(pw.JSONField):
    """Backwards compatibility only: use `peewee.JSONField`.

    Peewee's `JSONField` with the encoder the old Proper field used as the
    default `dumps`/`loads` (dates stored as `"__dt__<iso>"` strings and
    loaded back as `date`/`datetime`), so the data stored with it keeps
    loading the same.
    """

    def __init__(self, dumps=None, loads=None, **kwargs):
        super().__init__(
            dumps=dumps or jsonplus.dumps,
            loads=loads or jsonplus.loads,
            **kwargs,
        )
