from [[ app_name ]].app import db
from [[ app_name ]].models.concerns import Timestamped


class StorageBlob(Timestamped, db.Model):
    __tablename__ = "storage_blobs"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(255), nullable=False, index=True)
    service_name = db.Column(db.String(255), nullable=False)
    byte_size = db.Column(db.Integer, nullable=False)
    content_type = db.Column(db.String(255), nullable=False)
    checksum = db.Column(db.String(255))
    metadata = db.Column(db.JSON)
