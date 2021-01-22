from [[ name ]].models import Post

from .application import ApplicationController


class Posts(ApplicationController):

    def index(self, req, resp):
        self.latest = Post.latest()
        resp.fresh_when(self.latest, public=True)

    def show(self, req, resp, id, slug):
        self.post = Post.first_or_not_found(id=id)
        if self.post.slug != slug:
            resp.redirect_to("Posts.show", self.post)
            return

        resp.template = f"posts/show-{self.post.type}"
        resp.fresh_when(self.post, public=True)

    def feed(self, req, resp):
        posts = Post.latest()
        if resp.fresh_when(self.posts, public=True):
            return
        resp.headers.update({
            "content-type": "application/rss",
            "content-disposition": 'attachment; filename="feed.rss"'
        })
        resp.template = "posts/feed"
        resp.format = "rss"
