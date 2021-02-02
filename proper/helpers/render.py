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

    def __init__(self, templates, **envops):
        self.loader = jinja2.FileSystemLoader(str(templates))
        self.env = jinja2.Environment(
            loader=self.loader,
            autoescape=jinja2.select_autoescape(default=True),
            **envops
        )

    def __call__(self, relpath, **context):
        return self.render(relpath + ".jinja")

    def render(self, relpath, **context):
        tmpl = self.env.get_template(relpath)
        return tmpl.render(**context)


def render_folder(src, dst, data, *, envops=None, force=False):
    envops = envops or {}
    jinja_render = Render(src, **envops)
