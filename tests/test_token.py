"""Tests for ProperModel.generate_token / resolve_token and the named token_for variants."""

import peewee as pw
import pytest
from playhouse.sqlite_ext import SqliteExtDatabase

from proper import App, current
from proper.models import ProperModel
from proper.units import HOURS


# ── helpers ─────────────────────────────────────────────────────────

db = SqliteExtDatabase(":memory:")


class BaseModel(ProperModel):
    class Meta:
        database = db


class Item(BaseModel):
    name = pw.CharField()


class Account(BaseModel):
    email = pw.CharField()
    password = pw.CharField(default="hashed-pw-abc123")

    def generate_token_for_password_reset(self):
        return (self.password or "")[-10:]

    def generate_token_for_email_verification(self):
        return self.email


@pytest.fixture(autouse=True)
def setup():
    config = {
        "SECRET_KEYS": ["x" * 50],
        "DEBUG": False,
    }
    app = App("tests", config)
    current.app = app

    db.connect(reuse_if_open=True)
    db.create_tables([Item, Account])
    yield
    db.drop_tables([Item, Account])


# ═══════════════════════════════════════════════════════════════════
# generate_token / resolve_token (low-level)
# ═══════════════════════════════════════════════════════════════════


class TestGenerateToken:
    def test_returns_string(self):
        item = Item.create(name="thing")
        token = item.generate_token()
        assert isinstance(token, str)
        assert len(token) > 0

    def test_different_records_produce_different_tokens(self):
        a = Item.create(name="a")
        b = Item.create(name="b")
        assert a.generate_token() != b.generate_token()

    def test_same_record_produces_different_tokens_with_different_salts(self):
        item = Item.create(name="thing")
        t1 = item.generate_token(salt="purpose-a")
        t2 = item.generate_token(salt="purpose-b")
        assert t1 != t2


class TestResolveToken:
    def test_round_trip(self):
        item = Item.create(name="thing")
        token = item.generate_token()
        found = Item.resolve_token(token)
        assert found is not None
        assert found.id == item.id

    def test_expired_token_returns_none(self):
        item = Item.create(name="thing")
        token = item.generate_token()
        # itsdangerous uses floor-second timestamps, so sleep past the boundary
        import time
        time.sleep(2.1)
        found = Item.resolve_token(token, max_age=1)
        assert found is None

    def test_tampered_token_returns_none(self):
        item = Item.create(name="thing")
        token = item.generate_token()
        found = Item.resolve_token(token + "x")
        assert found is None

    def test_deleted_record_returns_none(self):
        item = Item.create(name="thing")
        token = item.generate_token()
        item.delete_instance()
        found = Item.resolve_token(token)
        assert found is None

    def test_wrong_salt_returns_none(self):
        item = Item.create(name="thing")
        token = item.generate_token(salt="purpose-a")
        found = Item.resolve_token(token, salt="purpose-b")
        assert found is None

    def test_default_salt_is_class_name(self):
        item = Item.create(name="thing")
        token = item.generate_token()
        # Resolve with explicit salt matching the class name should work
        found = Item.resolve_token(token, salt="Item")
        assert found is not None
        assert found.id == item.id

    def test_with_fingerprint(self):
        item = Item.create(name="thing")

        def fp(x):
            return x.name

        token = item.generate_token(fp)
        found = Item.resolve_token(token, fp)
        assert found is not None
        assert found.id == item.id

    def test_fingerprint_mismatch_returns_none(self):
        item = Item.create(name="thing")

        def fp(x):
            return x.name

        token = item.generate_token(fp)
        # Change the record so fingerprint no longer matches
        item.name = "changed"
        item.save()
        found = Item.resolve_token(token, fp)
        assert found is None

    def test_cross_model_token_returns_none(self):
        """Token for one model class cannot resolve on another."""
        item = Item.create(name="thing")
        token = item.generate_token()
        # Account has a different default salt (class name)
        found = Account.resolve_token(token)
        assert found is None


# ═══════════════════════════════════════════════════════════════════
# generate_token_for / resolve_token_for (named tokens)
# ═══════════════════════════════════════════════════════════════════


class TestGenerateTokenFor:
    def test_returns_string(self):
        acct = Account.create(email="alice@test.com")
        token = acct.generate_token_for("password_reset")
        assert isinstance(token, str)

    def test_different_names_produce_different_tokens(self):
        acct = Account.create(email="alice@test.com")
        t1 = acct.generate_token_for("password_reset")
        t2 = acct.generate_token_for("email_verification")
        assert t1 != t2

    def test_missing_method_raises_attribute_error(self):
        item = Item.create(name="thing")
        with pytest.raises(AttributeError):
            item.generate_token_for("nonexistent")


class TestResolveTokenFor:
    def test_round_trip(self):
        acct = Account.create(email="alice@test.com")
        token = acct.generate_token_for("password_reset")
        found = Account.resolve_token_for("password_reset", token, max_age=1 * HOURS)
        assert found is not None
        assert found.id == acct.id

    def test_expired_token_returns_none(self):
        acct = Account.create(email="alice@test.com")
        token = acct.generate_token_for("password_reset")
        import time
        time.sleep(2.1)
        found = Account.resolve_token_for("password_reset", token, max_age=1)
        assert found is None

    def test_wrong_name_returns_none(self):
        acct = Account.create(email="alice@test.com")
        token = acct.generate_token_for("password_reset")
        found = Account.resolve_token_for("email_verification", token, max_age=1 * HOURS)
        assert found is None

    def test_fingerprint_invalidation_on_password_change(self):
        acct = Account.create(email="alice@test.com", password="original-secret")
        token = acct.generate_token_for("password_reset")
        # Change the password so the last 10 chars differ
        acct.password = "completely-different"
        acct.save()
        found = Account.resolve_token_for("password_reset", token, max_age=1 * HOURS)
        assert found is None

    def test_fingerprint_invalidation_on_email_change(self):
        acct = Account.create(email="alice@test.com")
        token = acct.generate_token_for("email_verification")
        # Change the email, invalidating the fingerprint
        acct.email = "bob@test.com"
        acct.save()
        found = Account.resolve_token_for("email_verification", token, max_age=1 * HOURS)
        assert found is None

    def test_fingerprint_still_valid_when_unchanged(self):
        acct = Account.create(email="alice@test.com")
        token = acct.generate_token_for("email_verification")
        # Modify something else, fingerprint should still match
        acct.password = "different-password"
        acct.save()
        found = Account.resolve_token_for("email_verification", token, max_age=1 * HOURS)
        assert found is not None
        assert found.id == acct.id

    def test_deleted_record_returns_none(self):
        acct = Account.create(email="alice@test.com")
        token = acct.generate_token_for("password_reset")
        acct.delete_instance()
        found = Account.resolve_token_for("password_reset", token, max_age=1 * HOURS)
        assert found is None

    def test_tampered_token_returns_none(self):
        acct = Account.create(email="alice@test.com")
        token = acct.generate_token_for("password_reset")
        found = Account.resolve_token_for("password_reset", token + "x", max_age=1 * HOURS)
        assert found is None
