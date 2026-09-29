# Micro-benchmarks

In-process measurements of the framework alone: no server, one thread, a
few thousand iterations, best of five. They exist to answer "what did this
change buy" for the parts of a request that the cross-framework harness
(the `proper-bench` repo) does not exercise, and they are what the numbers
in `PLAN_COMPILE.md` came from.

```sh
uv run python benchmarks/micro/dispatch.py   # a request through a controller with callbacks and an inferred view
uv run python benchmarks/micro/routes.py     # router.match and url_for with 50 resources registered
uv run python benchmarks/micro/views.py      # compiling a catalog of 41 views with minijx, first and steady renders
```

Compare against the previous commit with `git stash`, run, `git stash pop`,
run again. The absolute numbers depend on the interpreter: this repo's venv
is CPython 3.14 with the GIL; `proper-bench` runs the free-threaded build,
and its venv can run these too:

```sh
uv run --project ~/Code/proper-bench python benchmarks/micro/dispatch.py
```
