<h1><img src="https://properproject.org/proper.svg" height="48" />
Proper Web Framework</h1>

Proper is a new Python web framework. Not another Flask clone, it's a Ruby-on-Rails clone :P.

More seriously: it isn't a clone, but it is heavily influenced by Rails in the ways that matter: opinionated, generator-heavy, focused on REST and server-rendered HTML, built around a fixed project structure, and packed with batteries for auth, file uploads, etc.

The one thing Proper does very differently: The runtime is ASGI (you need it for performance and WebSockets), but the code you write is _synchronous_. No `async`/`await` confetti scattered across code that doesn't need concurrency.

Full human-shaped docs at [properproject.org/docs](https://properproject.org/docs).

## For the press release

> Proper is the Python web framework I built for myself after years in the trade, once I understood that hard conventions do not lock you in — they free you to focus on what's important.

(It also works for the back cover of my future biography by Walter Isaacson).

## Community

- [Discord](https://discord.gg/aWVP3F4abD)

## License

Code: [MIT](https://github.com/jpsca/proper/blob/main/MIT-LICENSE). Documentation: [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
