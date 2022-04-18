from sqlalchemy import select, update
from sqla_wrapper import SQLAlchemy


class Blob:
    id: int = 0
    key: str = ""
    service_name: str = ""
    filename: str = ""
    byte_size: int = 0
    content_type: str = ""
    checksum: str = ""
    data: dict

    def __init__(self, **kw):
        self.data = {}
        self.update(kw)

    @property
    def attached(self) -> bool:
        return self.id > 0

    def update(self, kw):
        for name, value in kw.items():
            setattr(self, name, value)

    def load_from_db(self, db: "SQLAlchemy", blob_id: int) -> "Blob":
        blobs_table = db.registry.metadata.tables["storage_blobs"]
        row = db.s.execute(
            select(blobs_table)
            .where(blobs_table.c.id == blob_id)
        ).fetchone()
        return self.update(row._mapping)

    def save_to_db(self, db: "SQLAlchemy") -> None:
        assert self.id
        blobs_table = db.registry.metadata.tables["storage_blobs"]
        db.s.execute(
            update(blobs_table)
            .where(blobs_table.c.id == self.id)
            .values(data=self.data)
        )
        db.s.commit()
