from .concern import Concern


__all__ = ("CurrentTimezone", )


class CurrentTimezone(Concern):
    @property
    def etag(self):
        from proper import current
        return f"{super().etag}-{current.timezone}".strip("-")

    def before(self):
        from proper import current
        current.timezone = self._get_timezone()

    # Private

    def _get_timezone(self):
        from proper import current

        return (
            # Always prefer the timezone from the URL
            self.params.get("timezone")

            # else, get it from a cookie
            or self.request.get_cookie("timezone")

            # else, use the user-defined locale
            # (delete or modify to fit your user model)
            or (current.user is not None and getattr(current.user, "timezone", None))

            # else, fallback to the default locale
            or self.app.config.TIMEZONE_DEFAULT
        )
