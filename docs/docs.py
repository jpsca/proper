"""
# WriteaDoc Documentation

- `python docs.py run` to start a local server with live reload.
- `python docs.py build` to build the documentation for deployment.

"""
from writeadoc import Docs


site = {
    "name": "Proper",
    "description": "Opinionated and batteries-included Python web framework. Made for people who read their code.",
    "base_url": "https://properproject.org",
    "lang": "en",
    "source_code": "https://github.com/jpsca/proper/",
}

pages = [
    "docs_index.md",
    "getting_started.md",
    "tutorial.md",
    {
        "title": "Models",
        "pages": [
            "models.md",
            "relationships.md",
            "migrations.md",
        ]
    },
    {
        "title": "Controllers",
        "pages": [
            "controllers.md",
            "routing.md",
            "forms.md",
            "assets.md",
            "controllers_advanced.md",
        ]
    },
    {
        "title": "Views",
        "pages": [
            "jx_components.md",
            "form_rendering.md",
        ]
    },
    {
        "title": "Other Components",
        "pages": [
            "authentication.md",
            "storage.md",
            "tasks.md",
            "i18n.md",
            "emails.md",
            "channels.md",
        ]
    },
    {
        "title": "Going to Production",
        "pages": [
            "caching.md",
            "security.md",
            "deployment.md",
        ]
    },
    {
        "title": "Digging Deeper",
        "pages": [
            "testing.md",
            "advanced_models.md",
            "api.md",
        ]
    },
]

docs = Docs(
    __file__,
    pages=pages,
    site=site,
)


if __name__ == "__main__":
    docs.cli()
