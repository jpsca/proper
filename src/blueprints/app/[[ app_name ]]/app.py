from proper import App


app = App(__name__)
config = app.config

if app.catalog:
    app.catalog.add_folder(app.components_path / "common")
