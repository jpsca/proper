> :warning: WARNING: This is a work in progress. It doesn't have documentation. Do NOT use it.

# Proper

A web framework optimized for programmer happiness.


### Requirements

- Python 3.6+


### Installation

	pip install proper


## Design principles

- "Convention over configuration".

- No globals.
	When you need a shared object, pass it arround.

- Optimize for the 95%.
	Don't compromise the usability of the common cases to keep consistency
	with the edge cases.

- Code redability is important.

- App-code over framework-code
	Because app code is infintely configurable without dirty hacks.

- "Everyone is an adult here".
	Run with scissors if you must.

- Regular WSGI is great.


# Sources of inspirations

## From Elixir/Phoenix

### Pipelines in the routes.

You don't need to have a framework for APIs and other for full-fletched apps, you can just deactivate cookie sessions, flash messages and other things yoi don't need for specific sections of your sites.
And is super easy to add things too like admin-only sections just by composing multiple pipelines, after all, there are just lists of callables.

### App-code over framework-code.

You can make it clean and straightforward or you can make it configurable.
But if you put the code in the application, thanks to a standarized project skeleton,
you can have both!


## From Ruby/Rails

### Convention over configuration.

### Optimize for developer happiness.

### The application code must be beatiful.

- Empty class-based controllers that works!
- Class-based controllers allows several tricks that make the experience much better:
	- A configurable and plugganle render and view functions.
	- Class based views a-la Django, but simpler and completely obvious because is your application code (see (App-code over framework-code)
	- Saving context varaibles in your controller instance looks much cleaner that building a dictionary and manually calling render and the end of each controller.
