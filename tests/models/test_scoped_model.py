import peewee as pw
import pytest
from peewee import ModelSelect

from proper.models import ScopedSelect, scope


@pytest.fixture()
def Article(db, BaseModel):
    class Article(BaseModel):
        title = pw.CharField()
        status = pw.CharField(default="draft")
        views = pw.IntegerField(default=0)
        category = pw.CharField(default="general")

        @scope
        def published(cls, query):
            return query.where(cls.status == "published")

        @scope
        def draft(cls, query):
            return query.where(cls.status == "draft")

        @scope
        def popular(cls, query, min_views=1000):
            return query.where(cls.views >= min_views)

        @scope
        def in_category(cls, query, cat):
            return query.where(cls.category == cat)

        @scope
        def top(cls, query, n=10):
            return query.order_by(cls.views.desc()).limit(n)

    db.create_tables([Article])
    return Article


@pytest.fixture()
def User(db, BaseModel):
    class User(BaseModel):
        username = pw.CharField(unique=True)
        is_active = pw.BooleanField(default=True)
        role = pw.CharField(default="user")

        @scope
        def active(cls, query):
            return query.where(cls.is_active == True)  # noqa: E712

        @scope
        def admins(cls, query):
            return query.where(cls.role == "admin")

        @scope
        def by_name(cls, query):
            return query.order_by(cls.username)

    db.create_tables([User])
    return User


@pytest.fixture()
def Comment(db, BaseModel, Article, User):
    class Comment(BaseModel):
        article = pw.ForeignKeyField(Article, backref="comments")
        user = pw.ForeignKeyField(User, backref="comments")
        body = pw.TextField()
        approved = pw.BooleanField(default=False)

        @scope
        def approved_only(cls, query):
            return query.where(cls.approved == True)  # noqa: E712

        @scope
        def pending(cls, query):
            return query.where(cls.approved == False)  # noqa: E712

    db.create_tables([Comment])
    return Comment


class TestScope:
    def test_select_returns_scoped_select(self, Article):
        query = Article.select()
        assert isinstance(query, ScopedSelect)

    def test_scope_is_classmethod(self, Article):
        assert isinstance(Article.__dict__["published"], classmethod)
        assert Article.published.__self__ is Article

    def test_single_scope(self, Article):
        Article.create(title="A", status="published")
        Article.create(title="B", status="draft")

        results = list(Article.select().published())
        assert len(results) == 1
        assert results[0].title == "A"

    def test_chained_scopes(self, Article):
        Article.create(title="A", status="published", views=500, category="tech")
        Article.create(title="B", status="published", views=2000, category="tech")
        Article.create(title="C", status="published", views=2000, category="science")
        Article.create(title="D", status="draft", views=5000, category="tech")

        results = list(
            Article.select().published().popular(1000).in_category("tech")
        )
        assert len(results) == 1
        assert results[0].title == "B"

    def test_scope_with_default_arg(self, Article):
        Article.create(title="A", views=999)
        Article.create(title="B", views=1000)
        Article.create(title="C", views=5000)

        results = list(Article.select().popular())
        assert len(results) == 2

    def test_scope_with_custom_arg(self, Article):
        Article.create(title="A", views=100)
        Article.create(title="B", views=500)

        results = list(Article.select().popular(min_views=200))
        assert len(results) == 1
        assert results[0].title == "B"

    def test_scope_with_limit(self, Article):
        for i in range(5):
            Article.create(title=f"Art {i}", views=i * 100)

        results = list(Article.select().top(3))
        assert len(results) == 3
        assert results[0].views == 400

    def test_scopes_independent_per_model(self, Article, User):
        """Each model has its own scopes, not shared."""
        query = Article.select()
        assert hasattr(query, "published")
        assert not hasattr(query, "active")

        query = User.select()
        assert hasattr(query, "active")
        assert not hasattr(query, "published")


class TestScopePreservation:
    def test_scopes_survive_where(self, Article):
        Article.create(title="Python Tips", status="published", views=2000)
        Article.create(title="Python Tricks", status="published", views=50)
        Article.create(title="Go Tips", status="draft", views=3000)

        results = list(
            Article.select()
            .published()
            .where(Article.title.contains("Python"))
            .popular(100)
        )
        assert len(results) == 1
        assert results[0].title == "Python Tips"

    def test_scopes_survive_paginate(self, Article):
        for i in range(15):
            Article.create(title=f"Art {i}", status="published")

        results = list(Article.select().published().paginate(1, 5))
        assert len(results) == 5

    def test_scopes_survive_order_by(self, Article):
        Article.create(title="B", status="published")
        Article.create(title="A", status="published")
        Article.create(title="C", status="draft")

        results = list(
            Article.select()
            .published()
            .order_by(Article.title)
        )
        assert len(results) == 2
        assert results[0].title == "A"

    def test_scopes_survive_join(self, Article, User, Comment):
        user = User.create(username="alice", is_active=True)
        a1 = Article.create(title="A", status="published")
        a2 = Article.create(title="B", status="draft")
        Comment.create(article=a1, user=user, body="Nice", approved=True)
        Comment.create(article=a2, user=user, body="Meh", approved=True)
        Comment.create(article=a1, user=user, body="Spam", approved=False)

        results = list(
            Comment.select()
            .approved_only()
            .join(Article)
            .where(Article.status == "published")
        )
        assert len(results) == 1
        assert results[0].body == "Nice"

    def test_scopes_survive_count(self, Article):
        Article.create(title="A", status="published")
        Article.create(title="B", status="published")
        Article.create(title="C", status="draft")

        assert Article.select().published().count() == 2

    def test_scopes_survive_switch(self, Article, User, Comment):
        user = User.create(username="alice", is_active=True)
        art = Article.create(title="A", status="published")
        Comment.create(article=art, user=user, body="Hi", approved=True)

        results = list(
            Comment.select()
            .approved_only()
            .join(Article)
            .switch(Comment)
            .join(User)
            .where(User.is_active == True)  # noqa: E712
        )
        assert len(results) == 1


class TestQueryReuse:
    def test_base_query_reuse(self, Article):
        Article.create(title="T1", status="published", views=100, category="tech")
        Article.create(title="T2", status="published", views=200, category="tech")
        Article.create(title="S1", status="published", views=300, category="science")
        Article.create(title="D1", status="draft", views=500, category="tech")

        base = Article.select().published()
        tech = list(base.in_category("tech"))
        science = list(base.in_category("science"))

        assert len(tech) == 2
        assert len(science) == 1
        assert science[0].title == "S1"


class TestScopedSelectWrapper:
    def test_wrapper_returns_non_query_result_as_is(self, Article):
        """When a wrapped method returns a non-ModelSelect (e.g. count()),
        the wrapper returns the value without modification."""
        Article.create(title="A", status="published")
        Article.create(title="B", status="draft")

        result = Article.select().published().count()
        assert result == 1
        assert isinstance(result, int)

    def test_wrapper_upgrades_plain_model_select(self, Article):
        """When a wrapped method returns a plain ModelSelect (not a
        ScopedSelect subclass), it gets upgraded with scopes bound."""
        q = Article.select()
        # Inject a callable that returns a plain ModelSelect to simulate
        # a peewee method that creates a fresh query internally.
        q.fresh = lambda: ModelSelect(Article, [Article.title])
        result = q.fresh()
        assert isinstance(result, ScopedSelect)
        assert result._scopes == q._scopes

    def test_no_scopes_returns_method_as_is(self, Article):
        """ScopedSelect with empty scopes returns methods without wrapping."""
        q = ScopedSelect(Article, [Article.title])
        q._bind_scopes({})
        # Calling a public method should work and return without wrapping
        result = q.where(Article.title == "x")
        assert isinstance(result, ModelSelect)


class TestModelWithoutScopes:
    def test_model_without_scopes_works(self, db, BaseModel):
        """A ProperModel with no @scope methods works like a normal Model."""

        class Plain(BaseModel):
            name = pw.CharField()

            class Meta:
                table_name = "plain"

        db.create_tables([Plain])
        try:
            Plain.create(name="hello")
            assert Plain.select().count() == 1
        finally:
            db.drop_tables([Plain])
