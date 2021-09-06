from [[ app_name ]].models.base import Base, db
from [[ app_name ]].models.mixins import Timestamped


class [[ class_name ]](Base, Timestamped):
    __tablename__ = "[[ table_name ]]"

    id = db.Column(db.Integer, primary_key=True)
    [%- for row in rows %]
    [[ row | safe ]]
    [%- endfor %]
