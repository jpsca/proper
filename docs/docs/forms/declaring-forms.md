
# Declaring forms

At the heart of Proper forms is the `Form` class. A form contain your field definitions, delegate validation, take input, and in general function as the glue holding everything together.

Forms are classes that inherit from the `proper.forms.Form` class. You then create instances of those classes in your controllers, using the request and maybe object data.

```python
from proper.forms import Form, Email, Password

class LoginForm(Form):
    login = Email(required=True)
    password = Password(required=True)
```

## Form attributes

```python
Form(input_data=None, object=None, *, prefix="")
```

### input_data

The data from `request.form`.

### object

Pre-existing data used to populate the form. This can be a dictionary or an instance of a class, typically an ORM Model.

### prefix

Optional namespace for the form.


## Form methods

### validate()

[ TODO ]

### save()

[ TODO ]

### create_object()

[ TODO ]

### update_object()

[ TODO ]

### load_data()

This method can be used to replace the data passed when instantiating the form.
Eg:

```python
form = Form()
...
form.load_data(input_data, object_data)
```
