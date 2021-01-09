import pyceo

from proper import generators as g
from proper import static


class Cli:
    def __init__(self, app):
        self.app = app

    @property
    def ApplicationCli(self):

        class ApplicationCli(pyceo.Cli):
            """Application-specific commands.

            You don't need a special console to interact with the app,
            just run `ipython` or the regular python interpreter and import
            the application, like a regular python package.

            """

            g = self.GeneratorsCli
            static = self.StaticCli

        return ApplicationCli

    @property
    def GeneratorsCli(self):
        class GeneratorsCli(pyceo.Cli):
            """Generate new code.
            """

            _root_path = self.app.root_path

            def controller(self, name):
                """Generates a new controller.

                This includes a controller file and the default templates.

                Arguments:
                - name: PascalCased name of the controller class

                """
                g.controller(self._root_path, name=name)

            def resource(self, name):
                """Generates a new resource.

                This include a model, controller, templates, and
                a resource route in the `routes.py` file

                Arguments:
                - name: PascalCased name of the resource class

                """
                pass

        return GeneratorsCli

    @property
    def StaticCli(self):
        class StaticCli(pyceo.Cli):
            """Manage static files.
            """

            _root_path = self.app.root_path

            def clean(self):
                """Delete all digested and compressed assets in static/public.
                """
                static.clean(self._root_path)

            def compile(self):
                """Digest and compress the assets in static/public.
                """
                static.compile(self._root_path)

        return StaticCli
