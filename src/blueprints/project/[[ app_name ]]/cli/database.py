from proper_cli import Cli

from ..models import BaseModel
from ..app import app


class DB(Cli):
    def create_tables(self):
        """Create tables for all models"""
        with app.db.connection_context():
            for model in BaseModel.__subclasses__():
                print(f"Creating table `{model._meta.table_name}`...")
                model.create_table(safe=True)


app.Cli.db = DB
