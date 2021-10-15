
# ORM integration

Proper forms can create and update entries in your database automatically if you tell it what ORM model to use.

Your form need to define a `_model` attribute with the model (a class) that will be intantiated with the form data. For example, with SQLAlchemy:

```python
from proper.forms import Form
from .models import session, MyModel

class SomethingForm(Form):
    _model = MyModel
    …

form = SomethingForm(data)
new_object = form.save()

# You still need to add it to the session and commit
session.add(new_object)
session.commit()
```
