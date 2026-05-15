from proper import TestClient

from [[ app_name ]].main import app
# from [[ app_name ]].models import [[ name_pascal ]]

client = TestClient(app)


[% if "index" in actions -%]
def test_[[ name_snake ]]_index(dbs):
    # [[ name_pascal ]].create( ... )
    response = client.get("/[[ plural_snake ]]")
    assert response.status == 200
    # assert "lorem ipsum" in response.body

[% endif %]
[% if "show" in actions -%]
def test_[[ name_snake ]]_show(dbs):
    # [[ name_pascal ]].create( ... )
    # response = client.get("/[[ plural_snake ]]/1")
    # assert response.status == 200
    # assert "lorem ipsum" in response.body
    pass

[% endif %]
[% if "new" in actions -%]
def test_[[ name_snake ]]_new():
    response = client.get("/[[ plural_snake ]]/new")
    assert response.status == 200
    # assert "lorem ipsum" in response.body

[% endif %]
[% if "edit" in actions -%]
def test_[[ name_snake ]]_edit(dbs):
    # [[ name_pascal ]].create( ... )
    # response = client.get("/[[ plural_snake ]]/1/edit")
    # assert response.status == 200
    # assert "lorem ipsum" in response.body
    pass

[% endif %]
[% if "create" in actions -%]
def test_[[ name_snake ]]_create(dbs):
    # response = client.post("/[[ plural_snake ]]", body={ ... })
    # assert response.status == 303
    # # assert that the object was created
    # [[ name_pascal ]].select()
    pass

[% endif %]
[% if "update" in actions -%]
def test_[[ name_snake ]]_update(dbs):
    # [[ name_pascal ]].create( ... )
    # response = client.patch("/[[ plural_snake ]]/1", body={ ... })
    # assert response.status == 303
    # # assert that the object was updated
    # [[ name_pascal ]].select(...)
    pass

[% endif %]
[% if "delete" in actions -%]
def test_[[ name_snake ]]_delete(dbs):
    # [[ name_pascal ]].create( ... )
    # response = client.delete("/[[ plural_snake ]]/1")
    # assert response.status == 303
    # # assert that the object was deleted
    # [[ name_pascal ]].select(...)
    pass

[% endif %]