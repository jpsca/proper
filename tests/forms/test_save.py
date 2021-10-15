import proper.forms as f


class Person:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class PersonForm(f.Form):
    _model = Person

    name = f.Text(required=True)
    age = f.Integer(required=True)


def test_save_and_create():
    input_data = {
        "name": "Jesse Montgomery III",
        "age": 23,
    }
    form = PersonForm(input_data)
    assert form.validate()

    obj = form.save()
    assert isinstance(obj, Person)
    assert obj.name == input_data["name"]
    assert obj.age == input_data["age"]


def test_save_and_update():
    input_data = {
        "name": "George",
        "age": 42,
    }
    p1 = Person(name="James", age=23)
    form = PersonForm(input_data, p1)
    assert form.validate()

    obj = form.save()
    assert isinstance(obj, Person)
    assert obj.name == input_data["name"]
    assert obj.age == input_data["age"]


def test_save_when_invalid():
    input_data = {"age": "NOT AN INTEGER"}
    form = PersonForm(input_data)
    assert form.save() is None


def test_no_model_no_created_object():
    class NoModelForm(PersonForm):
        _model = None

    input_data = {"name": "lorem ipsum", "age": "5"}
    form = NoModelForm(input_data)
    obj = form.save()

    assert obj == {"name": "lorem ipsum", "age": 5}


def test_no_model_no_updated_object():
    class NoModelForm(PersonForm):
        _model = None

    input_data = {"a": "lorem ipsum", "b": "5"}
    myobj = Person(name="old value", age=0)

    form = NoModelForm(input_data, myobj)
    obj = form.save()

    assert obj != myobj
