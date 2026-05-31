---
title: Proper Docs
description: |
  This is the documentation for Proper. These guides are designed to make you immediately productive with Proper, and to help you understand how all of the pieces fit together.
view: page_index.jx
---

# Proper Docs

This is the documentation for **Proper**. These guides are designed to make you immediately productive with Proper, and to help you understand how all of the pieces fit together.


## Start Here

### [Getting Started](/docs/getting_started)

Read me first. This will teach you how to set up a new Proper application.

### [Tutorial](#)

:::wip | Work in progress
:::

## Models

### [Peewee ORM](/docs/models)

Peewee ORM allows your models to talk to the application's database. This guide will get you started with models, the conventions Proper layers on top of Peewee, and how to create, load, update, and delete records.

### [Relationships and Joins](/docs/relationships)

Most applications have models that are connected to each other: a post has comments, a user has posts. This guide shows you how to declare those relationships, follow them in your code, and read them back from the database without doing extra work.

### [Database Migrations](/docs/migrations)

Migrations are how you change your database over time - adding tables, adding columns, renaming things - without losing the data you already have. This guide shows you how to create, apply, and roll back migrations using the `proper db` command.


## Controllers

### [Controllers Overview](/docs/controllers)

Controllers receive web requests and decide what to do with them. This guide covers writing actions, reading parameters, rendering responses, redirecting, callbacks, and the tools for working with sessions, cookies, and flash messages.

### [Routing](/docs/routing)

The router is what connects an incoming URL like `/posts/12` to the right piece of your code. This guide explains how to write routes, how to generate URLs from your code, and how to inspect the routes your application has.

### [Working with Forms](/docs/forms)

Forms are how users send data into your application, and Formidable is the library Proper uses to define and validate them. This guide covers how to declare forms, validate input, save the results, and wire them into controllers.

### [Static Assets](/docs/assets)

Static assets are the CSS files, JavaScript files, images, and fonts your pages need. This guide explains how Proper serves them, and how filename fingerprinting lets browsers cache them aggressively without ever showing a stale version.

### [Controllers Advanced Topics](/docs/controllers_advanced)

The Controllers Overview covered the day-to-day shape of a controller. This guide picks up where it stops - the topics that don't come up on every page, but that you will reach for sooner or later: HTTP errors, custom error handlers, wiring an error tracker for production, conditional GETs, file downloads, controllers that don't fit the CRUD mold, and the harder corners of rate limiting.


## Views

### [Jx Components and Layouts](/docs/jx_components)

Jx components are the pieces of Python that produce the HTML your users see in the browser. This guide covers writing components with props, slots, and content; how layouts wrap your pages; how Proper picks which template to render; and how to break a page up into reusable parts.

### [Rendering Forms](/docs/form_rendering)

The HTML side of forms: how to render fields with the built-in helpers, how to write the markup yourself, the wire format that comes back, and the rendering patterns for sub-forms, nested forms, file uploads, and the method-override trick for `PATCH` / `PUT` / `DELETE`.


## Other Components

### [Authentication](/docs/authentication)

Authentication is how your application knows which user is making a request. This guide walks you through Proper's built-in `auth` addon, which gives you registration, login, password reset, and rate limiting out of the box.

### [File Storage](/docs/storage)

Most applications eventually need to let users upload files - profile pictures, attachments, documents. This guide shows you how to attach files to your models, store them on disk or in S3, and serve them back safely.

### [Background Tasks](/docs/tasks)

Some work doesn't belong in a web request: sending an email, processing a video, calling a slow third-party API. This guide introduces Huey, the task queue Proper uses, and shows you how to define tasks, schedule them, and run the workers that process them.

### [Internationalization (i18n)](/docs/i18n)

Internationalization, often shortened to i18n, is the work of preparing your application to be translated into other languages. This guide covers locale-aware routing, where translations live, how pluralization works, and how to format dates and numbers for the user's locale.

### [Rich Text](/docs/rich_text)

How to store, render, and edit rich text content in Proper, including embedded image and file attachments.

### [Sending Emails](/docs/emails)

Sooner or later your application will need to send email - confirmations, password resets, notifications. This guide covers writing emails as Jx components, configuring SMTP for production and console output for development, and sending them in the background.

### [Channels](/docs/channels)

:::wip | Work in progress
:::

Channels let your application push data to the browser in real time over a WebSocket connection, instead of waiting for the user to refresh. This guide covers writing channels, broadcasting messages, and tracking who is currently connected.


## Going to Production

### [Caching](/docs/caching)

Caching is the art of doing the same expensive work only once. This guide introduces Proper's SQLite and Redis cache stores, shows you how to cache fragments of pages, and explains how to use HTTP cache headers so the browser does some of the work for you.

### [Security](/docs/security)

:::wip | Work in progress
:::

Putting an application on the public internet means thinking about people who would like to break it. This guide covers the protections Proper gives you out of the box - CSRF, origin checks, rate limiting, secure sessions, safe password handling - and the parts you have to think about yourself.

### [Deployment and Performance](/docs/deployment)

:::wip | Work in progress
:::

Going to production means picking an ASGI server, deciding how many workers to run, serving your static files efficiently, and managing environment variables. This guide will help you make those choices and keep your application fast under real traffic.


## Digging Deeper

### [Testing Proper Applications](/docs/testing)

Tests give you the confidence to change your code without breaking it. This guide introduces Proper's `TestClient`, which lets you simulate HTTP requests, upload files, exercise WebSockets, and sign users in - all without running a real server.

### [Models Advanced Topics](/docs/advanced_models)

A handful of model patterns that don't come up every day, but are worth having documented for when they do: composite primary keys, circular foreign keys, polymorphic relationships, and using more than one database in the same application.

### [Building API-only Applications](/docs/api)

:::wip | Work in progress
:::

<!--
### [The Proper CLI](#)

:::wip | Work in progress
:::

The `proper` command-line tool is what you use to scaffold code, run the dev server, manage the database, and inspect your application. This guide walks through how to use it and how to add your own commands to it.
-->

----