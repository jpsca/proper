# Locales folder

Files in the config/locales folder are used for internationalization and
are automatically loaded by Proper. If you want to use locales other than
English, add the necessary files in this directory.

To use the locales, use `app.i18n`:

```python
app.i18n("hello")
```

In views, this is aliased to just `_`:

```html+jinja
{{ _('hello') }}
```

The default `en.yml` locale in this directory contains a sample pair of translation strings:

```yaml
en:
  hello: "Hello world"
```

This means, that in the `"en"` locale, the key `hello` will map to the `"Hello world"` string.
When the current locale is `"en"`, this:

```html+jinja
<h1>{{ _('hello') }}</h1>
```

will render as

```html
<h1>Hello world</h1>
```

To learn more about the API, please read the Proper Internationalization guide
at https://guides.properweb.org/i18n.

Be aware that YAML interprets the following case-insensitive strings as
booleans: `true`, `false`, `on`, `off`, `yes`, `no`. Therefore, these strings
must be quoted to be interpreted as strings. For example:

```yaml
en:
  "yes": yup
  enabled: "ON"
```
