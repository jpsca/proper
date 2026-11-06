"""The queries of the migrator for MySQL and MariaDB.

There is no server: the connection records the queries. These are the ones
that a MySQL 8.4 and a MariaDB 11.8 ran when the tests were written.
"""

import peewee as pw
import pytest

from proper.models.migrate import Migrator


FOREIGN_KEYS = "information_schema.key_column_usage"


@pytest.fixture
def dburl():
    return "mysql://localhost/fake"


@pytest.fixture
def connection(database):
    return database.connection()


@pytest.fixture
def migrator(database, connection):
    migrator = Migrator(database)

    @migrator.create_model
    class Author(pw.Model):
        name = pw.CharField()

    @migrator.create_model
    class Post(pw.Model):
        title = pw.CharField(max_length=100, unique=True)
        author = pw.ForeignKeyField(Author, null=True)

    migrator()
    connection.queries.clear()
    return migrator


def changes(connection):
    """The queries that change the schema."""
    return [query for query in connection.queries if FOREIGN_KEYS not in query]


def describe(connection, *columns):
    """Set the columns that `DESCRIBE` answers with: the name, definition,
    null, key, default and extra of each."""
    connection.results["DESCRIBE"] = columns


def test_change_fields(migrator, connection):
    describe(connection, ("title", "varchar(200)", "YES", "UNI", None, ""))

    migrator.change_fields("post", title=pw.CharField(max_length=200, unique=True))
    migrator()

    assert changes(connection) == [
        "ALTER TABLE `post` MODIFY COLUMN `title` VARCHAR(200)",
        "DESCRIBE `post`;",
        "ALTER TABLE `post` MODIFY `title` varchar(200) NOT NULL",
    ]


def test_change_fields_replaces_the_index(migrator, connection):
    describe(connection, ("title", "varchar(100)", "YES", "UNI", None, ""))

    migrator.change_fields("post", title=pw.CharField(max_length=100, index=True))
    migrator()

    assert changes(connection)[-2:] == [
        "DROP INDEX `post_title` ON `post`",
        "CREATE INDEX `post_title` ON `post` (`title`)",
    ]


def test_a_unique_column_is_not_made_unique_again(migrator, connection):
    """MySQL makes one more unique index each time it reads `UNIQUE` in
    the definition of a column."""
    describe(connection, ("title", "varchar(100)", "NO", "UNI", None, ""))

    migrator.drop_not_null("post", "title")
    migrator.add_not_null("post", "title")
    migrator.rename_field("post", "title", "name")
    migrator()

    assert [query for query in changes(connection) if "DESCRIBE" not in query] == [
        "ALTER TABLE `post` MODIFY `title` varchar(100) NULL",
        "ALTER TABLE `post` MODIFY `title` varchar(100) NOT NULL",
        "ALTER TABLE `post` CHANGE `title` `name` varchar(100) NOT NULL",
    ]


def test_add_not_null(migrator, connection):
    describe(connection, ("title", "varchar(100)", "YES", "", None, ""))

    migrator.add_not_null("post", "title")
    migrator()

    assert changes(connection) == [
        "DESCRIBE `post`;",
        "ALTER TABLE `post` MODIFY `title` varchar(100) NOT NULL",
    ]


def test_remove_a_foreign_key(migrator, connection):
    """The index of a foreign key is dropped with its column: MySQL refuses
    to drop it before."""
    connection.results[FOREIGN_KEYS] = [
        ("author_id", "author", "id", "fk_post_author_id_refs_author", "RESTRICT", "RESTRICT")
    ]

    migrator.remove_fields("post", "author")
    migrator()

    assert changes(connection) == [
        "ALTER TABLE `post` DROP FOREIGN KEY `fk_post_author_id_refs_author`",
        "ALTER TABLE `post` DROP COLUMN `author_id` CASCADE",
    ]
