## [[app_name]]

This is a Proper-based web application. Proper is an opinionated, batteries-included Python web framework. It runs only on free-threaded Python (3.14t and later), on Linux (or WSL, or a container), and serves WSGI with Bearings. It uses synchronous controllers, Peewee ORM, Huey task queue, Jx components, and Formidable forms.

Deep reference docs are bundled in the `proper` skill.

## Key Conventions

- **Everything is CRUD** - controllers map to RESTful resource actions (index, new, create, show, edit, update, delete)
- **Singular names** - resource/model/controller names are always singular (e.g., `Post`, not `Posts`)
- **Boot order matters** - `__init__.py` imports: main → router → controllers → models → tasks. New controllers/models must be imported in their respective `__init__.py` (the generators add these imports for you)
- **`form.save()` persists** - for a form with `Meta.orm_cls`, it creates or updates the model instance, saves it in a transaction, and returns it; no follow-up `instance.save()` is needed
- **Controllers are sync** - controller methods are regular sync Python, with no `async`/`await`
- **`current` context** - `current.request`, `current.user`, `current.auth_session` available in controllers and templates

## Common Commands

```bash
proper g resource Post title:str body:text       # Generate full CRUD resource
proper g model Photo title:str published:bool    # Generate model only
proper install auth|storage|i18n|channels        # Install addons
proper db migrate                                # Run migrations
proper check                                     # Find the mistakes of the app before it runs
uv run proper run                                # Start dev server
```

## File Organization

What                 | Where                                       | Also modify
-------------------- | ----------------------------------          | -------------------------
Controller           | `controllers/{name}_controller.py`          | `controllers/__init__.py`
Model                | `models/{name}.py`                          | `models/__init__.py`
Form                 | `forms/{name}.py`                           | -
Views                | `views/{name}/*.jx`                         | -
Concern (controller) | `controllers/concerns/{name}.py`            | controller that uses it
Concern (model)      | `models/concerns/{name}.py`                 | model that uses it
Task                 | `tasks/{name}.py`                           | -
Email                | `emails/{name}.py`/`views/emails/{name}.jx` | -
Config               | `config/{name}.py`                          | `config/__init__.py`

## General Guidelines

- Before suggesting removal or simplification of existing configuration (editable installs, specific build steps, etc.), ask the user first. Do not proactively remove things that look unnecessary.

## Writing / Editing

- Unless done to avoid recursive imports, place all the imports at the beginning of the file.
- After creating or updating a python file, run `uv run ruff check --fix ${file} 2>/dev/null || true` to fix any linting errors.
- Never disable any linter errors without user confirmation.

## Testing

- Always run `uv run pytest` as the test runner command. Do not use `pytest` directly or any other test runner unless explicitly told otherwise.
- Never remove or disable any tests without user confirmation.
- When writing tests, use real filesystem and real objects instead of mocks unless it requires running separated service or asked to mock. Avoid unittest.mock patterns for integration-style tests.
- When debugging test failures, check for framework-specific behaviors
- After a change, run `uv run proper check` and fix every error it lists

## Dependencies

- Use `uv add <package>` to add dependencies. Do not manually edit pyproject.toml for adding requirements.
