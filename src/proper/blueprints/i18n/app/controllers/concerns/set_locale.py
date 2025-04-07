from proper import Controller

from app.main import app


class SetLocale:
    def __call__(self, co: Controller):
        assert app.i18n
        co.request.locale = (
            # Always prefer the locale from the URL
            co.params.get("locale")

            # else, use the user-defined locale
            # (delete or modify to fit your user model)
            or co.request.user and getattr(co.request.user, "locale", None)

            # else, find the best match between the translations available and the
            # requested locales from the `accept-language` HTTP header
            or app.i18n.negotiate_locale(co.request.accept_language)

            # else, fallback to the default locale
            or app.config.LOCALE_DEFAULT
        )
