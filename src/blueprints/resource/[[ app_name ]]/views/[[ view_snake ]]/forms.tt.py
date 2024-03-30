from pydantic import BaseModel

from [[ app_name ]].models import [[ singular_pascal ]]


@as_form(orm=[[ singular_pascal ]])
class [[ form_class ]](BaseModel):
    [% for f in form_fields %]
    [[ f.name ]]: [[ f.type ]]([% if f.default %] = [[ f.default ]][% endif %])
    [%- endfor %]
