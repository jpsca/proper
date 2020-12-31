import jinja2


class Render:
    @property
    def globals(self):
        return self.env.globals

    @property
    def filters(self):
        return self.env.filters

    @property
    def tests(self):
        return self.env.tests

    def __init__(self, templates):
        loader = jinja2.FileSystemLoader(str(templates))
        self.env = jinja2.Environment(
            loader=loader,
            autoescape=jinja2.select_autoescape(default=True),
        )

    def __call__(self, relpath, **context):
        tmpl = self.env.get_template(relpath + ".jinja")
        return tmpl.render(**context)
