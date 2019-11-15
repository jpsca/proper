from pony.orm import Database

from ..app import config


db = Database()

db.bind(
    provider=config.database.provider,
    user=config.database.username,
    password=config.database.password if config.database.password else "",
    host=config.database.host if config.database.host else "",
    port=config.database.port if config.database.port else "",
    database=config.database.name,
)
