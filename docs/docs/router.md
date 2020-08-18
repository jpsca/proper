
# Router

## The Purpose of a router

Although they look similar, an URL path like `/hello/world` in Proper (as in most modern frameworks) it doesn't match a `word` file in a `hello` folder. You can connect that URL to the code that will answer that request.

That is what the Proper router does: recognizes URLs and dispatches them to a controller's action; or redirect you to another URL or another application. It can also generate URLs for you, avoiding the need to hardcode strings in your views.

### Connecting URLs to Code

When your Proper application receives an incoming request for:

```ruby
GET /product/42
```

it asks the router to match it to a controller action. If the first matching route is:

```python hl_lines="2"
router.routes = [
    get("/product/:id", to="Products.show"),
   ...
]
```

the request is dispatched to the product controller's show action with `{"id": "42"}` as argument.
