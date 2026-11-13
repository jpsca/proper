---
title: Generators
description: `proper g model|resource|controller|seed|email|channel`: attribute syntax (`title:str,unique`, `user:fk-User,backref:comments`), `--only`/`--exclude`, `--namespace`, `--migration`
last_verified: 2026-11-13
sources:
  - src/proper/generators
  - src/proper/_blueprints/controller
  - src/proper/_blueprints/model
  - src/proper/_blueprints/email
  - src/proper/_blueprints/channel
---

# Generators

What `proper g` writes and the syntax of its arguments.

## Generators

### Generating a Model

The model generator creates a model file and registers it in `models/__init__.py`:

```bash
proper g model Photo title:str description:text published:bool
```

This generates `models/photo.py`:

```python
import peewee as pw

from .base import BaseModel


class Photo(BaseModel):
    title = pw.CharField()
    description = pw.TextField()
    published = pw.BooleanField()
```

#### Field Type Shortcuts

The generator supports these type names:

| Type shortcut | Peewee Field          |
|---------------|-----------------------|
| `str`         | `CharField()`         |
| `text`        | `TextField()`         |
| `int`         | `IntegerField()`      |
| `bigint`      | `BigIntegerField()`   |
| `float`       | `FloatField()`        |
| `decimal`     | `DecimalField()`      |
| `bool`        | `BooleanField()`      |
| `date`        | `DateField()`         |
| `datetime`    | `DateTimeField()`     |
| `time`        | `TimeField()`         |
| `uuid`        | `UUIDField()`         |
| `blob`        | `BlobField()`         |
| `fk`          | `ForeignKeyField()`   |

If you omit the type, it defaults to `str` (CharField).

Some aliases are also accepted: `string`/`char` for `str`, `boolean` for `bool`, `integer` for `int`, `binary` for `blob`, `numeric` for `decimal`.

#### Field Options

Add options after the type, separated by commas:

```bash
proper g model Photo title:str,unique views:int,default:0 description:text,null
```

This generates:

```python
class Photo(BaseModel):
    title = pw.CharField(unique=True)
    views = pw.IntegerField(default=0)
    description = pw.TextField(null=True)
```

Options without a value default to `True`. You can use any Peewee field option: `null`, `unique`, `index`, `default`, `primary_key`, etc.

#### Foreign Keys

Use `fk-ModelName` as the type. Add `backref` and other options with commas:

```bash
proper g model Comment body:text user:fk-User,backref:comments photo:fk-Photo,backref:comments,on_delete:CASCADE
```

This generates:

```python
class Comment(BaseModel):
    body = pw.TextField()
    user = pw.ForeignKeyField(User, backref="comments")
    photo = pw.ForeignKeyField(Photo, backref="comments", on_delete="CASCADE")
```

The generated module imports the related models (`from .photo import Photo`, `from .user import User`, sorted with `from .base import BaseModel`). A foreign key to the model itself is written as `pw.ForeignKeyField("self", ...)`.

#### Generating with a Migration

Add `--migration` to also create a migration file:

```bash
proper g model Photo title:str description:text --migration
```

### Generating a Full Resource

The resource generator creates a model, controller, form, and views all at once:

```bash
proper g resource Photo title:str description:text published:bool
```

This generates:

- `models/photo.py` - the model
- `controllers/photo_controller.py` - a CRUD controller with all actions
- `forms/photo.py` - a form class linked to the model
- `views/photo/` - Jx templates for index, show, new and edit, plus a shared `form.jx` partial (delete is a button in `show`)
- `tests/controllers/test_photo.py` - a test skeleton

You can limit which actions are generated:

```bash
# Only generate index and show
proper g resource Photo title:str --only=index,show

# Generate everything except delete
proper g resource Photo title:str --exclude=delete

# Singular resource (no index, no :id in URLs), mounted at the singular name: /profile
proper g resource Profile --singular

# Name of the id segment in member URLs (/photos/:uuid instead of /photos/:photo_id); ignored with --singular
proper g resource Photo title:str --pk=uuid

# Include a migration
proper g resource Photo title:str --migration
```

### Generating a Controller

`proper g controller NAME` creates a controller, a form, views and `tests/controllers/test_<name>.py` without a model (or uses the model of the same name when `models/__init__.py` imports one). The same `--only`/`--exclude` options apply; with `--namespace`, no test file is written.

```bash
proper g controller Dashboard --only=index
proper g controller Post --namespace=admin      # controllers/admin/, forms/admin/, views/admin/, and admin_router = router.scope("admin") in router.py if missing (see namespacing.md)
proper g controller card/closure                # controllers/card/closure_controller.py (pk=None, under cards/:card_id), controllers/concerns/card_scoped.py if missing, tests/controllers/test_closure.py; no form or views; routes named Card:Closure.* (see controllers.md)
```

### Other Generators

```bash
proper g seed roles            # db/seeds/roles.py; --db NAME (other than main) writes db/seeds/NAME/roles.py (see migrations.md)
proper g email Welcome         # emails/welcome_email.py (WelcomeEmail) + views/emails/welcome.jx (see emails.md)
proper g channel Chat          # channels/chat_channel.py (see channels.md)
```

Every generator accepts `--help`. The model, controller, resource, email and channel generators take `--force` to overwrite existing files without asking. Read the generated files before editing them, and check that `controllers/__init__.py` / `models/__init__.py` got the new import.
