"""The pages of the toolbar. Imported only when the toolbar is installed."""
from proper import Controller
from proper.errors import NotFound
from .toolbar import URL_PREFIX, render


PREFIX = URL_PREFIX.strip("/")


class DebugToolbarController(Controller):
    @classmethod
    def connect(cls, router):
        router.get(PREFIX)(cls.index)
        router.get(f"{PREFIX}/:request_id/summary")(cls.summary)
        router.get(f"{PREFIX}/:request_id")(cls.show)

    @property
    def toolbar(self):
        toolbar = self.app.debug_toolbar
        if toolbar is None or not toolbar.enabled:
            raise NotFound()
        return toolbar

    def index(self):
        return render("index.html", records=self.toolbar.store.latest())

    def summary(self):
        """What the bar shows of a request made by the page (a Turbo Frame,
        a Turbo Stream), as JSON."""
        record = self.toolbar.store.get(self.params["request_id"])
        if record is None:
            raise NotFound()
        return self.render(json={
            "id": record.id,
            "status": record.status,
            "kind": record.kind,
            "method": record.method,
            "path": record.path,
            "ms": round(record.ms, 1),
            "sql": len(record.app_queries),
            "prefetch": record.prefetch,
        })

    def show(self):
        toolbar = self.toolbar
        record = toolbar.store.get(self.params["request_id"])
        if record is None:
            self.response.status = 404
            return render("missing.html", size=toolbar.store.size)
        slowest = max((query.ms for query in record.queries), default=0)
        store = toolbar.store
        return render(
            "show.html",
            record=record,
            previous=store.get(record.redirected_from) if record.redirected_from else None,
            slowest=slowest,
            steps_ms=sum(ms for _name, ms in record.steps),
        )
