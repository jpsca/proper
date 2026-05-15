<h1><img src="https://properproject.org/proper.svg" height="48" />
Proper Web Framework</h1>

Proper is a new Python web framework. Not another Flask clone, it's a Ruby-on-Rails clone :P.

More seriously: it isn't a clone, but it is heavily influenced by Rails in the ways that matter. Very opinionated, generator-heavy, focused on REST and server-rendered HTML, built around a fixed project structure, and packed with hardcoded batteries. You *can* swap pieces if you must, but the assumption is that you won't.

The one thing Proper does very differently: **sync above, async below**. The runtime is ASGI (you need it for performance and WebSockets), but the code you write is _synchronous_. No `async`/`await` confetti scattered across code that doesn't need concurrency.


## Quick start

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/).

```bash
uvx proper_new myapp
cd myapp
proper g resource Post title:str body:text
proper server
```

That's a working CRUD app with model, controller, views, routes, migrations, and tests.

Full (human-shaped) docs at [properproject.org/docs](https://properproject.org/docs).


## Why not X?

**Why not Flask?** - Absolute freedom means absolute chaos.

**Why not Django?** - Django gives you the pieces and expects you to assemble them; Proper assembles them and gives you direction.

**Why not FastAPI?** - FastAPI is awesome, but has the opposite shape: It's all about APIs and async-first, while Proper is server-rendered and sync-first. Building a React SPA on top of a JSON backend? You might want to use it. Building HTML for humans? Try Proper.

**Why Peewee instead of SQLAlchemy?** - Smaller surface area, more readable, and ActiveRecord-style scopes fit it cleanly. SQLAlchemy is excellent but not something I want to read every day.

**Why Jx instead of Jinja?** - Server-rendered Python components with typed props and slots. See the [Jx docs](https://properproject.org/docs/jx_components/) for the case.


## Built with AI agents in mind

Proper ships with an official skill: [properproject.org/skill.zip](https://properproject.org/skill.zip). Drop it in `~/.claude/skills/` and your agent will scaffold and edit your app the _Proper_ way (pun intended).

This isn't just an extra. Hard conventions are exactly what makes AI output legible to humans: fewer tokens to understand a project, fewer surprises in generated code, and less effort reviewing it.


## What's in the box

- **Peewee ORM** with migrations, query helpers, and connection handling
- **Forms** — declarative, validated, ORM-integrated, with rendering helpers
- **Jx components** — server-rendered Python components, typed props, slots
- **Caching** — fragment, action, and low-level, on SQLite or Redis
- **Background tasks** via Huey, with retries, schedules, and cron syntax
- **Authentication** — sessions, password resets, rate limiting, pwned-password checks
- **File storage** — disk and S3 adapters, signed URLs, image variants
- **i18n** — locale-aware routing, translations, pluralization, date formats
- **Email** — templated transactional mail, SMTP and console mailers
- **WebSockets** — channels, broadcasts, presence


## For the press release

> Proper is the Python web framework I built for myself after fifteen years in the trade, once I understood that hard conventions do not lock you in — they free you to focus on what's important.

(It also works for the back cover of my future biography by Walter Isaacson).


## Status

This is 0.9, I'll call it 1.0 when I've found more bugs. Bug reports and contributions are very welcome. File them at [github.com/jpsca/proper/issues](https://github.com/jpsca/proper/issues).


## Community

- [Discord](https://discord.gg/aWVP3F4abD)


## License

Code: [MIT](https://github.com/jpsca/proper/blob/main/MIT-LICENSE). Documentation: [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).

Made by [Juan-Pablo Scaletti](https://github.com/jpsca) in Lima, Perú.
