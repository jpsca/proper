import hyperform as f

from [[ app_name ]].models import db


class ModelForm(f.SQLAForm):
    _session = db.s
