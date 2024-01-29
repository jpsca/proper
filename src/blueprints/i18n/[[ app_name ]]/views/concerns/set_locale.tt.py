from proper import View

from [[ app_name ]].app import app


class SetLocale:
    def before(self, view: View):
        view.request.locale = (
            # Always prefer the locale from the URL
            view.params.get("locale")

            # else, use the user-defined locale
            # (delete or modify to fit your user model)
            or view.request.user and getattr(view.request.user, "locale")

            # else, find the best match between the translations available and the
            # requested locales from the `accept-language` HTTP header
            or app.i18n.negotiate_locale(view.request.accept_language)

            # else, fallback to the default locale
            or app.config.LOCALE_DEFAULT
        )

    def after(self, view: View):
        pass
