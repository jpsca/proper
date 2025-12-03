import formidable as f

from ..models import [[ name_pascal ]]


class [[ form_class ]](f.Form):
    class Meta:
        orm_cls = [[ name_pascal ]]

    [% for f in form_fields %]
    [[ f.name ]] = f.[[ f.type ]]([% if f.default %]default=[[ f.default ]][% endif %])
    [%- endfor %]
