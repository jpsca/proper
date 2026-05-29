---
title: Rich Text
description: |
  How to store, render, and edit rich text content in Proper, including embedded image and file attachments.
number_headers: true
---

# Rich Text

This guide covers Proper's rich text addon - a field type that stores
formatted documents with embedded attachments, plus a default editor
that knows how to produce and edit them.

After reading this guide, you will know:

- What rich text means in Proper, and how to install and configure it.
- How to create, render, style, and customize rich text content.
- How the bundled editor handles attachments.

The companion [File Storage](/docs/storage) guide covers attachments at the level rich text builds on. Read it first if you haven't met the `Attachment` model.

---

## Introduction

Proper's rich text addon facilitates the handling and display of text that includes formatting elements beyond plain text such as bold, italics, colors, hyperlinks, and tables.

It integrates a modern rich text editor called [Lexxy](https://basecamp.github.io/lexxy/) with tons of out-of-the-box features  including file uploads and embedding images. The editor can also be easily extended to add things like @mentions, emojis, or whatever advanced text feature your app might need.

:::figure | The default rich text editor
![Lexxy](/assets/images/rich_text/lexxy.png)
:::


## Setup


---

## Related

- [File Storage](/docs/storage) - the `Attachment` model and storage services rich text builds on.
- [Working with Forms](/docs/forms) - `JSONField` and form rendering.
