from .concern import Concern


__all__ = ("CurrentLocale", )


class CurrentLocale(Concern):
    @property
    def etag(self):
        return f"{super().etag}-{self._get_locale()}".strip("-")

    def before(self):
        self.request.locale = self._get_locale()
        super().before()

    # Private

    def _get_locale(self):
        return (
            # Always prefer the locale from the URL
            self.params.get("locale")

            # else, get it from a cookie
            or self.request.get_cookie("locale")

            # else, use the user-defined locale
            # (delete or modify to fit your user model)
            or (self.request.user is not None and getattr(self.request.user, "locale", None))

            # else, find the best match between the translations available and the
            # requested locales from the `accept-language` HTTP header
            or (self.app.i18n and self.app.i18n.negotiate_locale(self.request.accept_language))

            # else, fallback to the default locale
            or self.app.config.LOCALE_DEFAULT
        )
