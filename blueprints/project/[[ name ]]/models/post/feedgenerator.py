from datetime import timezone

from feedgen.feed import FeedGenerator

from [[ name ]].app import app


fg = FeedGenerator()
fg.id("https://jpscaletti.com")
fg.title("JP Scaletti")
fg.author({"name": "Juan Pablo Scaletti", "email": "juanpablo@jpscaletti.com"})
fg.link(href="https://jpscaletti.com", rel="alternate")
fg.language("en")


def create_feed(posts):
    fg.logo(app.url_static("images/logo.png", host=app.config.host))
    fg.link(href=f"{app.config.host}{app.url_for('Posts.feed')}", rel="self")

    for post in posts:
        fe = fg.add_entry()
        fe.content(content=post.html, type="CDATA")
        fe.id(f"{app.config.host}{app.url_for('Posts.show', slug=post.slug)}")
        fe.title(post.title)
        fe.published(post.published_at.astimezone(timezone.utc))
        fe.summary(post.description)
        fe.category([
            {
                "term": topic.slug,
                "scheme": f"{app.config.host}{app.url_for('Posts.topic', slug=topic.slug)}",
                "label": topic.name,
            }
            for topic in post.topics
        ])

    return fg.atom_str(pretty=True)
