---
title: Getting Started
description: |
  Setting up a new Proper application takes one command
number_headers: true
---

# Getting Started

Proper is a Python web framework that comes assembled.

A web application needs an ORM, a task queue, forms, authentication, storage, internationalization, and a view layer. Most frameworks give you the foundation and let you pick the rest. Proper picks them, wires    them together, and documents them here.   

The choices aren't there to lock you in. They're there so the first day of a project is spent writing code, not comparing database libraries.         

A good kitchen is opinionated. The knives live where the knives go. You work faster because you stop thinking about where the knives go. Proper works the same way.


## How to install Proper

How do you install `Proper`? That's the neat thing: **you don't**.

You don't even need a working Python interpreter, only the **uv** Python package manager. If you don't have it already, install it right now with just one command:

::: tab | Linux / macOS
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```
:::

::: tab | Windows
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```
:::

:::tip
uv can also be installed with Homebrew, among other ways. See the [uv installation page](https://docs.astral.sh/uv/getting-started/installation/){target=_blank}.
:::


## Starting a new web app

Run:

```bash
uvx proper_new myapp
```

`uvx` tells `uv` to fetch and run a one-off script. `proper_new` is that script. Its only job is to scaffold a new Proper application from a blueprint.

:::note
`myapp` becomes both the project folder and the importable Python package, so use lowercase ASCII letters and underscores.
:::

When the files are written, `proper_new` creates a virtual environment in `.venv` and installs the app's dependencies, including Proper itself.

The whole thing takes 10 to 20 seconds. Read the [tutorial](/docs/tutorial) next to see what's inside.

----

## AI Skill

Proper ships with a skill for AI agents like Claude Code. Install it once, and Claude understands Proper's idioms in every session.

Download [the skill](https://properproject.org/skill.zip) and unzip it into your skills folder — `.claude/skills`, for example.

```text
$ claude
╭─── Claude Code v5.6.789 ───────────────────────────╮
│                                                    │
│                       ▐▛███▜▌                      │
│                      ▝▜█████▛▘                     │
│                        ▘▘ ▝▝                       │
╰────────────────────────────────────────────────────╯

❯  Let's add an OAuth login with Google

... ✨ Magic happens ✨ ...
```

Claude reads your prompt, recognizes you're working in Proper, and applies the skill. No slash command, no prefix. Just describe what you want.
