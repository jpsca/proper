from [[ app_name ]].models.base import Base, db
from [[ app_name ]].models.mixins import Timestamped


class [[ singular_pascal ]](Base, Timestamped):
    __tablename__ = "[[ plural_snake ]]"

    id = db.Column(db.Integer, primary_key=True)
    [%- for row in rows %]
    [[ row | safe ]]
    [%- endfor %]
