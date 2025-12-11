# Translations folder

Proper adds all `.yml` files from this folder to the translations load path, automatically.

The default en.yml locale in this directory contains a sample pair of translation strings:

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
