from [[ name ]].models import Topic

from .application import ApplicationController


class Topics(ApplicationController):

    def show(self, req, resp, id, slug):
        self.topic = Topic.first_or_not_found(id=id)
        if self.topic.slug != slug:
            resp.redirect_to("Topics.show", self.topic)
            return

        resp.fresh_when(self.topic.posts, public=True)
