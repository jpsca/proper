> :warning: WARNING: This is a work in progress. It doesn't have documentation. Do NOT use it.

# Proper

A web framework optimized for programmer happiness.


### Requirements

- Python 3.10+


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

### App-code over framework-code.

You can make it clean and straightforward or you can make it configurable.
But if you put the code in the application, thanks to a standarized project skeleton,
you can have both!


## From Ruby/Rails

### Convention over configuration.

### Optimize for developer happiness.

### The application code must be beatiful.

- Empty class-based views that works!
- Class-based views allows several tricks that make the experience much better:
	- A configurable and plugganle render and view functions.
	- Class based views a-la Django, but simpler and completely obvious because is your application code (see (App-code over framework-code)
	- Saving context varaibles in your view instance looks much cleaner that building a dictionary and manually calling render and the end of each view.


![Visualization of the codebase](./diagram.svg)
