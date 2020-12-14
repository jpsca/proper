
# Router

## The Purpose of a router

Although they look similar, an URL path like `/hello/world` in Proper (as in most modern frameworks) it doesn't match a `word` file in a `hello` folder. You must connect that URL to some code that will answer that request.

That is what the Proper router does: recognizes URLs and dispatches them to a controller's action; or redirect you to another URL. It can also generate URLs for you from their names, avoiding the need to hardcode strings in your templates.

### Connecting URLs to Code

When your Proper application receives an incoming request for:

```ruby
GET /product/42
```

it asks the router to match it to a controller action. If the first matching route is:

```python hl_lines="3"
app.routes = [
    ...
    get("/products/:id", to="Products.show"),
   ...
]
```

the request is dispatched to the `Product` controller's `show` method with `id=42` as extra argument.

### Generating URLs

You can also generate an URL from its name.

```python
>>> app.url_for("Products.show", id=36)
/product/36
```

For the route above, its name is "Products.show", but you can also give it another name, which is very useful when you use the controller's action for other URLs:

```python
app.routes = [
    get("/products/:id", to="Products.show"),
    get("/products/latest", to="Products.show", name="latest_product"),  # weird but possible
]
```
```python
>>> app.url_for("latest_product")
/products/latest
```

If the route contains variables (like `:id`), you must specify values for them using keyword arguments:

```python
app.routes = [
    get("/posts/:id/:slug", to="Posts.show"),
]
```
```python
post = Post(id=123, slug="lorem-ipsum")

>>> app.url_for("Posts.show", id=post.id, slug=post.slug)
/posts/123/lorem-ipsum
```

However, if you have an object with attributes with the same names, you can simply pass that object instead of manually specify values every time:

```python
post = Post(id=123, slug="lorem-ipsum")

>>> app.url_for("Posts.show", post)
/posts/123/lorem-ipsum
```

This is not only faster (and less boring) to type, but also reduce the brittleness of your templates and makes your code easier to understand.


## Route Variables


### Built-in Converters


## HTTP Methods


## Resources


## Scopes


## Redirects

## Inspecting, and Testing Routes

