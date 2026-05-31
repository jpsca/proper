---
title: Proper Docs
description: |
  This is the documentation for Proper. These guides are designed to make you immediately productive with Proper, and to help you understand how all of the pieces fit together.
view: page_index.jx
---

# Proper Docs

This is the documentation for **Proper**. These guides are designed to make you immediately productive with Proper, and to help you understand how all of the pieces fit together.


## Start Here

<a href="/docs/getting_started" class="doc-index-section">
  <h3>Getting Started</h3>
  <p>Read me first. This will teach you how to set up a new Proper application.</p>
</a>

<a class="doc-index-section">
  <h3>Tutorial</h3>
  <section class="admonition wip">
    <p class="admonition-title">Work in progress</p>
  </section>
</a>

## Models

<a href="/docs/models" class="doc-index-section">
  <h3>Peewee ORM</h3>
  <p>Peewee ORM allows your models to talk to the application's database. This guide will get you started with models, the conventions Proper layers on top of Peewee, and how to create, load, update, and delete records.</p>
</a>

<a href="/docs/relationships" class="doc-index-section">
  <h3>Relationships and Joins</h3>
  <p>Most applications have models that are connected to each other: a post has comments, a user has posts. This guide shows you how to declare those relationships, follow them in your code, and read them back from the database without doing extra work.</p>
</a>

<a href="/docs/migrations" class="doc-index-section">
  <h3>Database Migrations</h3>
  <p>Migrations are how you change your database over time - adding tables, adding columns, renaming things - without losing the data you already have. This guide shows you how to create, apply, and roll back migrations using the <code>proper db</code> command.</p>
</a>


## Controllers

<a href="/docs/controllers" class="doc-index-section">
  <h3>Controllers Overview</h3>
  <p>Controllers receive web requests and decide what to do with them. This guide covers writing actions, reading parameters, rendering responses, redirecting, callbacks, and the tools for working with sessions, cookies, and flash messages.</p>
</a>

<a href="/docs/routing" class="doc-index-section">
  <h3>Routing</h3>
  <p>The router is what connects an incoming URL like <code>/posts/12</code> to the right piece of your code. This guide explains how to write routes, how to generate URLs from your code, and how to inspect the routes your application has.</p>
</a>

<a href="/docs/forms" class="doc-index-section">
  <h3>Working with Forms</h3>
  <p>Forms are how users send data into your application, and Formidable is the library Proper uses to define and validate them. This guide covers how to declare forms, validate input, save the results, and wire them into controllers.</p>
</a>

<a href="/docs/assets" class="doc-index-section">
  <h3>Static Assets</h3>
  <p>Static assets are the CSS files, JavaScript files, images, and fonts your pages need. This guide explains how Proper serves them, and how filename fingerprinting lets browsers cache them aggressively without ever showing a stale version.</p>
</a>

<a href="/docs/controllers_advanced" class="doc-index-section">
  <h3>Controllers Advanced Topics</h3>
  <p>The Controllers Overview covered the day-to-day shape of a controller. This guide picks up where it stops - the topics that don't come up on every page, but that you will reach for sooner or later: HTTP errors, custom error handlers, wiring an error tracker for production, conditional GETs, file downloads, controllers that don't fit the CRUD mold, and the harder corners of rate limiting.</p>
</a>


## Views

<a href="/docs/jx_components" class="doc-index-section">
  <h3>Jx Components and Layouts</h3>
  <p>Jx components are the pieces of Python that produce the HTML your users see in the browser. This guide covers writing components with props, slots, and content; how layouts wrap your pages; how Proper picks which template to render; and how to break a page up into reusable parts.</p>
</a>

<a href="/docs/form_rendering" class="doc-index-section">
  <h3>Rendering Forms</h3>
  <p>The HTML side of forms: how to render fields with the built-in helpers, how to write the markup yourself, the wire format that comes back, and the rendering patterns for sub-forms, nested forms, file uploads, and the method-override trick.</p>
</a>


## Other Components

<a href="/docs/authentication" class="doc-index-section">
  <h3>Authentication</h3>
  <p>Authentication is how your application knows which user is making a request. This guide walks you through Proper's built-in <code>auth</code> addon, which gives you registration, login, password reset, and rate limiting out of the box.</p>
</a>

<a href="/docs/storage" class="doc-index-section">
  <h3>File Storage</h3>
  <p>Most applications eventually need to let users upload files - profile pictures, attachments, documents. This guide shows you how to attach files to your models, store them on disk or in S3, and serve them back safely.</p>
</a>

<a href="/docs/tasks" class="doc-index-section">
  <h3>Background Tasks</h3>
  <p>Some work doesn't belong in a web request: sending an email, processing a video, calling a slow third-party API. This guide introduces Huey, the task queue Proper uses, and shows you how to define tasks, schedule them, and run the workers that process them.</p>
</a>

<a href="/docs/i18n" class="doc-index-section">
  <h3>Internationalization (i18n)</h3>
  <p>Internationalization, often shortened to i18n, is the work of preparing your application to be translated into other languages. This guide covers locale-aware routing, where translations live, how pluralization works, and how to format dates and numbers for the user's locale.</p>
</a>

<a href="/docs/rich_text" class="doc-index-section">
  <h3>Rich Text</h3>
  <p>How to store, render, and edit rich text content in Proper, including embedded image and file attachments.</p>
</a>

<a href="/docs/emails" class="doc-index-section">
  <h3>Sending Emails</h3>
  <p>Sooner or later your application will need to send email - confirmations, password resets, notifications. This guide covers writing emails as Jx components, configuring SMTP for production and console output for development, and sending them in the background.</p>
</a>

<a href="/docs/channels" class="doc-index-section">
  <h3>Channels</h3>
  <p>Channels let your application push data to the browser in real time over a WebSocket connection, instead of waiting for the user to refresh. This guide covers writing channels, broadcasting messages, and tracking who is currently connected.</p>
  <section class="admonition wip">
    <p class="admonition-title">Work in progress</p>
  </section>
</a>


## Going to Production

<a href="/docs/caching" class="doc-index-section">
  <h3>Caching</h3>
  <p>Caching is the art of doing the same expensive work only once. This guide introduces Proper's SQLite and Redis cache stores, shows you how to cache fragments of pages, and explains how to use HTTP cache headers so the browser does some of the work for you.</p>
</a>

<a href="/docs/security" class="doc-index-section">
  <h3>Security</h3>
  <p>Putting an application on the public internet means thinking about people who would like to break it. This guide covers the protections Proper gives you out of the box - CSRF, origin checks, rate limiting, secure sessions, safe password handling - and the parts you have to think about yourself.</p>
  <section class="admonition wip">
    <p class="admonition-title">Work in progress</p>
  </section>
</a>

<a href="/docs/deployment" class="doc-index-section">
  <h3>Deployment and Performance</h3>
  <p>Going to production means picking an ASGI server, deciding how many workers to run, serving your static files efficiently, and managing environment variables. This guide will help you make those choices and keep your application fast under real traffic.</p>
  <section class="admonition wip">
    <p class="admonition-title">Work in progress</p>
  </section>
</a>


## Digging Deeper

<a href="/docs/testing" class="doc-index-section">
  <h3>Testing Proper Applications</h3>
  <p>Tests give you the confidence to change your code without breaking it. This guide introduces Proper's <code>TestClient</code>, which lets you simulate HTTP requests, upload files, exercise WebSockets, and sign users in - all without running a real server.</p>
</a>

<a href="/docs/advanced_models" class="doc-index-section">
  <h3>Models Advanced Topics</h3>
  <p>A handful of model patterns that don't come up every day, but are worth having documented for when they do: composite primary keys, circular foreign keys, polymorphic relationships, and using more than one database in the same application.</p>
</a>

<a href="/docs/api" class="doc-index-section">
  <h3>Building API-only Applications</h3>
  <section class="admonition wip">
    <p class="admonition-title">Work in progress</p>
  </section>
</a>

<!--
<a class="doc-index-section">
  <h3>The Proper CLI</h3>
  <p>The <code>proper</code> command-line tool is what you use to scaffold code, run the dev server, manage the database, and inspect your application. This guide walks through how to use it and how to add your own commands to it.</p>
  <section class="admonition wip">
    <p class="admonition-title">Work in progress</p>
  </section>
</a>
-->

----