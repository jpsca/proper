from proper import forms as f
[% if has_model %]
from [[app_name]].models import [[name_pascal]]
[% endif %]

class [[form_class]](f.Form):
    [%- if has_model %]
    class Meta:
        orm_cls = [[name_pascal]]
[% endif %]
    [%- for f in form_fields %]
    [[f.name]] = f.[[f.type]]([% if f.default %]default=[[f.default]][% endif %])
    [%- endfor %]
    [%- if not has_model and not form_fields %]
    pass
    [%- endif %]
