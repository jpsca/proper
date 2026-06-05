from [[app_name]].main import app


[% if "index" in actions -%]
def test_[[name_snake]]_index([[test_client]]):
    # [[name_pascal]].create( ... )
    url = app.url_for("[[name_pascal]].index")
    response = [[test_client]].get(url)
    assert response.status == 200
    # assert "lorem ipsum" in response.body

[% endif %]
[% if "show" in actions -%]
def test_[[name_snake]]_show([[test_client]]):
    # [[name_snake]] = [[name_pascal]].create( ... )
    # url = app.url_for("[[name_pascal]].show", [[name_snake]])
    # response = [[test_client]].get(url)
    # assert response.status == 200
    # assert "lorem ipsum" in response.body
    pass

[% endif %]
[% if "new" in actions -%]
def test_[[name_snake]]_new([[test_client]]):
    response = [[test_client]].get(app.url_for("[[name_pascal]].new"))
    assert response.status == 200
    # assert "lorem ipsum" in response.body

[% endif %]
[% if "edit" in actions -%]
def test_[[name_snake]]_edit([[test_client]]):
    # [[name_snake]] = [[name_pascal]].create( ... )
    # url = app.url_for("[[name_pascal]].edit", [[name_snake]])
    # response = [[test_client]].get(url)
    # assert response.status == 200
    # assert "lorem ipsum" in response.body
    pass

[% endif %]
[% if "create" in actions -%]
def test_[[name_snake]]_create([[test_client]]):
    # url = app.url_for("[[name_pascal]].create")
    # response = [[test_client]].post(url, body={ ... })
    # assert response.status == 303
    # # assert that the object was created
    # [[name_pascal]].select()
    pass

[% endif %]
[% if "update" in actions -%]
def test_[[name_snake]]_update([[test_client]]):
    # [[name_snake]] = [[name_pascal]].create( ... )
    # url = app.url_for("[[name_pascal]].update", [[name_snake]])
    # response = [[test_client]].patch(url, body={ ... })
    # assert response.status == 303
    # # assert that the object was updated
    # [[name_pascal]].select(...)
    pass

[% endif %]
[% if "delete" in actions -%]
def test_[[name_snake]]_delete([[test_client]]):
    # [[name_snake]] = [[name_pascal]].create( ... )
    # url = app.url_for("[[name_pascal]].delete", [[name_snake]])
    # response = [[test_client]].delete(url)
    # assert response.status == 303
    # # assert that the object was deleted
    # [[name_pascal]].select(...)
    pass

[% endif %]