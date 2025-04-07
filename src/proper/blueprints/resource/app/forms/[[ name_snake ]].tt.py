import datetime

from fodantic import formable
from pydantic import BaseModel as Schema

from app.models import [[ name_pascal ]]


@formable(orm=[[ name_pascal ]])
class [[ form_class ]](Schema):
    [% for f in form_fields %]
    [% if f.type in ["date", "datetime"] -%]
        [[ f.name ]]: datetime.[[ f.type ]][% if f.default %] = [[ f.default ]][% endif %]
    [%- else -%]
        [[ f.name ]]: [[ f.type ]][% if f.default %] = [[ f.default ]][% endif %]
    [%- endif %]
    [%- endfor %]
