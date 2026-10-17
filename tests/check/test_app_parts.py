import formidable as f

from proper.check import ERROR, WARNING, Problem
from proper.check.app_parts import (
    check_config,
    check_emails,
    check_forms,
    check_locales,
    check_services,
    known_settings,
)
from .conftest import FILES, extend


class LooseForm(f.Form):
    """A form of another package, which is not checked."""

    nothing = f.TextField()

    class Meta:
        orm_cls = dict


def test_a_form_field_that_is_not_in_the_model(make_shop):
    app = make_shop(extend("shop/forms.py", """

        class SignUpForm(f.Form):
            login = f.TextField()


        class DraftForm(f.Form):
            title = f.TextField()
            titel = f.TextField()

            class Meta:
                orm_cls = Post
    """))
    [problem] = check_forms(app)
    assert problem == Problem(
        ERROR,
        "`DraftForm.titel` is not a field of Post: `save()` would drop its value",
        path="shop/forms.py",
        line=19,
    )


def test_an_email_without_a_template(make_shop):
    app = make_shop({
        "shop/emails/__init__.py": "from . import welcome_email, receipt_email, base_email  # noqa\n",
        "shop/emails/receipt_email.py": """
            from proper.emails import EmailMessage


            class ReceiptEmail(EmailMessage):
                pass


            class NoteEmail(EmailMessage):
                body = "A note"
        """,
        "shop/emails/base_email.py": """
            from proper.emails import EmailMessage


            class BaseEmail(EmailMessage):
                pass


            class AppEmail(EmailMessage):
                pass


            class SignedEmail(AppEmail):
                body = "Signed"
        """,
    })
    [problem] = check_emails(app)
    assert problem == Problem(
        ERROR,
        "ReceiptEmail has no body and no template: write shop/views/emails/receipt.jx "
        "or shop/views/emails/receipt.txt.jx",
        path="shop/emails/receipt_email.py",
        line=4,
    )


def test_a_setting_that_looks_like_a_typo(make_shop):
    app = make_shop({
        "shop/main.py": FILES["shop/main.py"].replace(
            '"DEBUG": False,', '"DEBUG": False,\n        "MAX_FORM_FEILDS": 500,'
        ),
        "shop/config/__init__.py": """
            from .main import *  # noqa
        """,
        "shop/config/main.py": """
            STRIPE_KEY = "sk_test"
            MAILER_DEFAUL_OPTIONS = {}
        """,
    })
    app.config["MAILER_DEFAUL_OPTIONS"] = {}
    app.config["STRIPE_KEY"] = "sk_test"
    assert check_config(app) == [
        Problem(WARNING, "unknown setting `MAX_FORM_FEILDS`: did you mean `MAX_FORM_FIELDS`?"),
        Problem(
            WARNING,
            "unknown setting `MAILER_DEFAUL_OPTIONS`: did you mean `MAILER_DEFAULT_OPTIONS`?",
            path="shop/config/main.py",
            line=2,
        ),
    ]


def test_settings_without_a_config_folder(make_shop):
    app = make_shop()
    app.config["CACHE_TIMEOUT_SECONDZ"] = 1
    app.config["CABLE_PORTS"] = 1
    [problem] = check_config(app)
    assert problem.path == ""
    assert "did you mean `CABLE_PORT`?" in problem.message


def test_known_settings():
    known = known_settings()
    for name in ("DEBUG", "DATABASES", "QUEUE", "CABLE", "MAILERS", "STORAGE", "AUTH_ROUNDS", "TRUSTED_ORIGINS"):
        assert name in known


def test_services(make_shop):
    app = make_shop({
        "shop/config/__init__.py": "",
        "shop/config/storage.py": """
            STORAGE = "cloud"
            STORAGES = {"local": {"type": "Disk"}, "media": {"type": "Dropbox"}}
            MAILERS = {"smtp": {"type": "proper.emails.NoSuchMailer"}, "bad": {"type": "nodots"}}
        """,
    })
    app.config.STORAGE = "cloud"
    app.config.STORAGES = {"local": {"type": "Disk"}, "media": {"type": "Dropbox"}}
    app.config.MAILERS = {
        "console": {"type": "proper.emails.ToConsoleMailer"},
        "smtp": {"type": "proper.emails.NoSuchMailer"},
        "bad": {"type": "nodots"},
    }
    problems = check_services(app)
    assert [(p.message.split(" (")[0], p.line) for p in problems] == [
        ("STORAGE is `cloud`, which is not in STORAGES", 1),
        ("STORAGES['media'] has the type `Dropbox`, which is not a storage service", 2),
        ("MAILERS['smtp'] has the type `proper.emails.NoSuchMailer`, which can't be imported", 3),
        ("MAILERS['bad'] has the type `nodots`, which can't be imported", 3),
    ]
    assert all(p.level == ERROR and p.path == "shop/config/storage.py" for p in problems)


def test_services_by_default(make_shop):
    app = make_shop()
    assert check_services(app) == []
    app.config.STORAGE = "cloud"
    app.config.STORAGES = {}
    [problem] = check_services(app)
    assert problem.message == "STORAGE is `cloud`, which is not in STORAGES (empty)"


def test_incomplete_locales(make_shop):
    app = make_shop({
        "shop/config/locales/en.yml": """
            en:
              title: Shop
              a: A
              b: B
              c: C
              d: D
              e: E
              f: F
        """,
        "shop/config/locales/es.yml": """
            es:
              title: Tienda
        """,
        "shop/config/locales/pt.yml": """
            pt:
              title: Loja
              a: A
              b: B
              c: C
              d: D
              e: E
        """,
    })
    assert check_locales(app) == [
        Problem(
            WARNING,
            "the locale `es` lacks 6 key(s) that another has: a, b, c, d, e and 1 more",
            path="shop/config/locales",
        ),
        Problem(WARNING, "the locale `pt` lacks 1 key(s) that another has: f", path="shop/config/locales"),
    ]


def test_complete_locales(make_shop):
    app = make_shop()
    assert check_locales(app) == []
    app.i18n = None
    assert check_locales(app) == []
