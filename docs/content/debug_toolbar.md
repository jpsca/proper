---
title: The Debug Toolbar
description: |
  How to see what each request of your app did while you develop it. Covers installing the debug toolbar, reading the bar, the page of a request (time, SQL queries, views, cache, logs), finding repeated queries, and the list of the last requests.
number_headers: true
---

# The Debug Toolbar

When a page is slow, the first question is "what did it do?". How many queries did it run? Which view took the time? Did it read the cache or miss it? You can answer with `print()` calls and by reading the log, but it is slow work, and you have to know where to look.

The debug toolbar answers those questions for every request. It adds a small bar at the bottom of each page with a summary, and keeps a full page of details for each of the last requests.

After reading this guide, you will know:

- How to install the toolbar in your app.
- How to read the bar and the page of a request.
- How to find a query that runs once per row (an "N+1").
- How to see the requests that have no page of their own, like a redirect or a Turbo Frame.

----

## Installing it

The toolbar is not installed by default. Add it in `main.py`, after the app is created:

```python {title="myapp/main.py"}
from proper import App

from . import config


app = App(__name__, config)

if app.config.DEBUG:
    app.install_debug_toolbar()
```

That is all. Reload any page and the bar is there.

:::warning | For development only
The toolbar shows the data of your requests to anyone who opens its pages, and it makes every request a little slower. Keep it behind `DEBUG`, as in the example.
:::

## The bar

[![A page with the debug toolbar at the bottom](/assets/images/debug_toolbar/bar.png)](/assets/images/debug_toolbar/bar.png){target=_blank}
From left to right, the bar shows:

- **The redirect that led here**, if there was one. In the picture, `303 GET /` means the browser asked for `/` and was sent to this page.
- **The status and the request**: `200`, `GET /books`, and the action that answered it.
- **The total time** the app took to answer.
- **The SQL queries**: how many, how long they took, and how many are repeated. This part turns yellow when there are repeated queries.
- **The view**: the time spent rendering.
- **The cache**: the number of calls, with the hits and the misses.
- **The log**: the number of warnings and errors written during the request.
- **Details** opens the page of this request, and **Requests** the list of the last ones. Both open in a new tab.
- **×** hides the bar until the next page.

When the page makes a request with Turbo (a Turbo Frame, a form that answers with a Turbo Stream), the bar shows that request too, with a link to its page.

## The page of a request

Click **Details** to see everything the request did. The page is at `/__debug__/<request id>`, and has one panel for each kind of work.

### Time

[![The header of the page of a request and the Time panel](/assets/images/debug_toolbar/request.png)](/assets/images/debug_toolbar/request.png){target=_blank}

The first panel shows how long each step of the request took. Almost always, the time is in `dispatch`: the step that runs your controller and renders the view. Below, "Inside that time" splits it into SQL, views and cache.

### SQL

[![The SQL panel, with repeated queries](/assets/images/debug_toolbar/sql.png)](/assets/images/debug_toolbar/sql.png){target=_blank}

Every query of the request, in the order they ran, with:

- Its time.
- Its parameters.
- The line of your app that ran it, like `store/controllers/book_controller.py:17 in index`.
- The component that was rendering, if the query ran inside a view.
- A `×8` mark if the same query ran 8 times in the request.

That mark is how you find an **N+1**: one query for the list, and then one more for each row. In the picture, the view shows the author of each book, and each `book.author` runs a query. The panel says where: `rendering book_card.jx`.

The fix is to load the authors with the books, in one query:

```python
# Before: one query for the books, and one per book for its author
self.books = Book.select()

# After: one query
self.books = Book.select(Book, Author).join(Author)
```

Reload the page and the mark is gone.

### Views

[![The Views panel, with the variables and the components](/assets/images/debug_toolbar/views.png)](/assets/images/debug_toolbar/views.png){target=_blank}

The view that was rendered, the variables it got, and the tree of the components it used. For each component you see its time, its own time (without the components inside it), and the queries it ran. A component rendered many times in a row, like a card in a list, is shown as one line with a count.

### Cache and Logs

[![The Cache and Logs panels](/assets/images/debug_toolbar/cache-logs.png)](/assets/images/debug_toolbar/cache-logs.png){target=_blank}

The **Cache** panel lists each call to `app.cache`, with its key and its time. A read says if it was a hit or a miss.

The **Logs** panel has the lines written to the log while the request was answered, with the moment each one was written. It shows the same lines your log shows: with `LOG_LEVEL = "info"`, the debug lines are not there.

### Request and Response

The last two panels show the data of the request (route, query, form, headers, cookies, session) and of the response (headers, session).

Passwords, tokens and other secrets are masked: you see `▒▒▒▒` instead of the value.

## The list of requests

[![The list of the last requests](/assets/images/debug_toolbar/requests.png)](/assets/images/debug_toolbar/requests.png){target=_blank}

Some requests have no page to put a bar on: a redirect, a Turbo Frame, a JSON response, an error. They are all at `/__debug__`, newest first. Click one to see its page.

The requests for your assets, and for the pages of the toolbar, are not in the list.

## Good to know

- The toolbar keeps the last 50 requests, in memory. Restarting the app clears them.
- With more than one process (`PROCESSES` over 1), each process keeps its own requests. The page of a request is found only when the same process answers.
- `app.install_debug_toolbar()` returns the toolbar, which is also at `app.debug_toolbar`. To stop recording for a while, set `app.debug_toolbar.enabled = False`.
