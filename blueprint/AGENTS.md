## About Proper

Proper is an opinionated, batteries-included Python web framework. It uses ASGI with sync Python controllers, Peewee ORM, Huey task queue, Jx components, and Formidable forms.

Deep reference docs are bundled in the `proper` skill.

## Key Conventions

- **Everything is CRUD** — controllers map to RESTful resource actions (index, new, create, show, edit, update, delete)
- **Singular names** — resource/model/controller names are always singular (e.g., `Post`, not `Posts`)
- **Boot order matters** — `__init__.py` imports: main → router → controllers → models → tasks. New controllers/models must be imported in their respective `__init__.py`
- **`form.save()` returns unsaved** — it returns a model instance that hasn't been persisted yet; call `instance.save()` to write to DB
- **Controllers are sync** — despite ASGI, controller methods are regular sync Python
- **`current` context** — `current.request`, `current.user`, `current.auth_session` available in controllers and templates

## Common Commands

```
proper g resource Post title:str body:text       # Generate full CRUD resource
proper g model Photo title:str published:bool    # Generate model only
proper install auth|storage|i18n|channels        # Install addons
proper db migrate                                # Run migrations
uv run proper run                                # Start dev server
```

## File Organization

| What                 | Where                              | Also modify                        |
| -------------------- | ---------------------------------- | ---------------------------------- |
| Controller           | `controllers/{name}_controller.py` | `controllers/__init__.py`          |
| Model                | `models/{name}.py`                 | `models/__init__.py`               |
| Form                 | `forms/{name}.py`                  | —                                  |
| Views                | `views/{name}/*.jx`       | —                                  |
| Concern (controller) | `controllers/concerns/{name}.py`   | controller that uses it            |
| Concern (model)      | `models/concerns/{name}.py`        | model that uses it                 |
| Task                 | `tasks/{name}.py`                  | —                                  |
| Email                | `emails/{name}.py` + `views/emails/{name}.jx` | —                    |
| Config               | `config/{name}.py`                 | `config/__init__.py`               |

## General Guidelines

Before suggesting removal or simplification of existing configuration (editable installs, specific build steps, etc.), ask the user first. Do not proactively remove things that look unnecessary.

## Writing / Editing

After creating or updating a python file, run `uv run ruff check --fix ${file} 2>/dev/null || true` to fix any linting errors.

Never disable any linter errors without user confirmation.

## Testing

Always run `uv run pytest` as the test runner command. Do not use `pytest` directly or any other test runner unless explicitly told otherwise.

Never remove or disable any tests without user confirmation.

When writing tests, use real filesystem and real objects instead of mocks unless it requires running separated service or asked to mock. Avoid unittest.mock patterns for integration-style tests.

When debugging test failures, check for framework-specific behaviors

## Dependencies

Use `uv add <package>` to add dependencies. Do not manually edit pyproject.toml for adding requirements.
