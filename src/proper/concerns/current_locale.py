from .concern import Concern


__all__ = ("CurrentLocale", )


class CurrentLocale(Concern):
    before = {"do": "_set_locale"}

    @property
    def etag(self):
        from proper import current
        return f"{super().etag}-{current.locale}".strip("-")

    # Private

    def _set_locale(self):
        from proper import current
        current.locale = self._get_locale()

    def _get_locale(self):
        from proper import current

        return (
            # Always prefer the locale from the URL
            self.params.get("locale")

            # else, get it from a cookie
            or self.request.get_cookie("locale")

            # else, use the user-defined locale
            # (delete or modify to fit your user model)
            or (current.user is not None and getattr(current.user, "locale", None))

            # else, find the best match between the translations available and the
            # requested locales from the `accept-language` HTTP header
            or (self.app.i18n and self.app.i18n.negotiate_locale(self.request.accept_language))

            # else, fallback to the default locale
            or self.app.config.LOCALE_DEFAULT
        )
