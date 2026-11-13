import peewee as pw

[% for line in imports -%]
[[line | safe]]
[% endfor %]

class [[name_pascal]](BaseModel):
    [%- for row in rows %]
    [[row | safe]]
    [%- endfor %]
