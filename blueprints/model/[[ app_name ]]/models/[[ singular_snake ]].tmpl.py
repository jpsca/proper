from [[ app_name ]].app import db
from [[ app_name ]].models.mixins import Timestamped


class [[ singular_pascal ]](Timestamped, db.Model):
    __tablename__ = "[[ plural_snake ]]"

    id = db.Column(db.Integer, primary_key=True)
    [%- for row in rows %]
    [[ row | safe ]]
    [%- endfor %]
