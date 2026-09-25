from proper import current
from proper.controller import Controller
from .models import Fortune


router = current.app.router


class BenchController(Controller):
    @router.get("plaintext")
    def plaintext(self):
        return self.render(text="Hello, World!")

    @router.get("json")
    def json(self):
        return self.render(json={"message": "Hello, World!"})

    @router.get("fortunes")
    def fortunes(self):
        rows = list(Fortune.select().dicts())
        rows.append({"id": 0, "message": "Additional fortune added at request time."})
        rows.sort(key=lambda r: r["message"])
        self.fortunes = rows
