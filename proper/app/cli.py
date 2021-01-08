import pyceo

from proper import generators as g


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
        app = self.app

        class GeneratorsCli(pyceo.Cli):
            """Generate new code.
            """

            def controller(self, name):
                """Generates a new controller.

                This includes a controller file and the default templates.

                Arguments:
                - name: PascalCased name of the controller class

                """
                g.controller(app.root_path, name=name)

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
        app = self.app

        class StaticCli(pyceo.Cli):
            """Manage static files.
            """

            def clean(self):
                """."""
                pass

            def precompile(self):
                """."""
                pass

        return StaticCli
