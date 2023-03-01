from datetime import datetime

from [[ app_name ]].app import db


class StorageAttachment(db.Model):
    __tablename__ = "storage_attachments"

    id = db.Column(db.Integer, primary_key=True)
    model_type = db.Column(db.String(255), null=False)
    column_name = db.Column(db.String(255), null=False)
    model_id = db.Column(db.Integer, null=False)
    blob_id = db.Column(db.Integer, db.ForeignKey("storage_blobs.id"))
    blob = db.relationship(
        "StorageBlob",
        backref="attachments",
        cascade="all, delete-orphan"
    )
    filename = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, null=False)


db.Index(
    "ix_storage_attachments_unique",
    StorageAttachment.model_type,
    StorageAttachment.model_id,
    StorageAttachment.column_name,
    StorageAttachment.blob_id,
    unique=True
)
