import threading

import peewee as pw
import pytest

from proper.models import signals
from proper.models.signals import (
    ModelSignal,
    after_create,
    after_delete,
    after_save,
    before_create,
    before_delete,
    before_save,
)


MODEL_SIGNALS = {
    "before_save": before_save,
    "before_create": before_create,
    "after_create": after_create,
    "after_save": after_save,
    "before_delete": before_delete,
    "after_delete": after_delete,
}

module_signal = ModelSignal()


@module_signal
def module_receiver(sender, instance):
    return "module"


@pytest.fixture(autouse=True)
def _restore_receivers():
    """The signals of the models are global: what a test connects is
    disconnected after it."""
    before = {
        name: (signal._receivers, signal._receiver_list)
        for name, signal in MODEL_SIGNALS.items()
    }
    yield
    for name, signal in MODEL_SIGNALS.items():
        signal._receivers, signal._receiver_list = before[name]


@pytest.fixture()
def signal():
    return ModelSignal()


@pytest.fixture()
def log():
    """The names of the signals of the models, in the order they fire."""
    calls = []

    def recorder(name):
        def receiver(sender, instance):
            calls.append(name)

        return receiver

    for name, model_signal in MODEL_SIGNALS.items():
        model_signal.connect(recorder(name))
    return calls


@pytest.fixture()
def Book(db, BaseModel):
    class Book(BaseModel):
        title = pw.CharField(default="untitled")

    db.create_tables([Book])
    return Book


class Thing:
    pass


class SubThing(Thing):
    pass


class Other:
    pass


# --- connect / disconnect / send ---


def test_receiver_gets_the_sender_the_instance_and_the_arguments(signal):
    calls = []

    def receiver(sender, instance, *args, **kwargs):
        calls.append((sender, instance, args, kwargs))
        return "done"

    signal.connect(receiver)
    thing = Thing()
    responses = signal.send(thing, 1, flag=True)

    assert calls == [(Thing, thing, (1,), {"flag": True})]
    assert responses == [(receiver, "done")]


def test_send_without_receivers(signal):
    assert signal.send(Thing()) == []


def test_send_takes_a_class(signal):
    calls = []
    signal.connect(lambda sender, instance: calls.append((sender, instance)))
    signal.send(Thing)
    assert calls == [(Thing, Thing)]


def test_receivers_run_in_the_order_they_were_connected(signal):
    calls = []
    signal.connect(lambda sender, instance: calls.append(1))
    signal.connect(lambda sender, instance: calls.append(2))
    signal.connect(lambda sender, instance: calls.append(3))
    signal.send(Thing())
    assert calls == [1, 2, 3]


def test_a_receiver_with_a_sender_only_hears_that_class(signal):
    calls = []
    signal.connect(lambda sender, instance: calls.append(sender), sender=Thing)
    signal.send(Other())
    assert calls == []
    signal.send(Thing())
    assert calls == [Thing]


def test_a_receiver_with_a_sender_hears_its_subclasses(signal):
    calls = []
    signal.connect(lambda sender, instance: calls.append(sender), sender=Thing)
    signal.send(SubThing())
    assert calls == [SubThing]


def test_a_receiver_of_a_subclass_does_not_hear_the_parent(signal):
    calls = []
    signal.connect(lambda sender, instance: calls.append(sender), sender=SubThing)
    signal.send(Thing())
    assert calls == []


def test_connecting_twice_fails(signal):
    def receiver(sender, instance):
        pass

    signal.connect(receiver)
    with pytest.raises(ValueError, match=r"sender=any\) already connected"):
        signal.connect(receiver)

    signal.connect(receiver, sender=Thing)
    with pytest.raises(ValueError, match="already connected"):
        signal.connect(receiver, sender=Thing)


def test_the_same_receiver_can_be_connected_for_several_senders(signal):
    calls = []

    def receiver(sender, instance):
        calls.append(sender)

    signal.connect(receiver, sender=Thing)
    signal.connect(receiver, sender=Other)
    signal.send(Thing())
    signal.send(Other())
    assert calls == [Thing, Other]


def test_disconnect(signal):
    calls = []

    def receiver(sender, instance):
        calls.append("gone")

    def other(sender, instance):
        calls.append("kept")

    signal.connect(receiver)
    signal.connect(other)
    signal.disconnect(receiver)
    signal.send(Thing())
    assert calls == ["kept"]

    # It can be connected again
    signal.connect(receiver)
    signal.send(Thing())
    assert calls == ["kept", "kept", "gone"]


def test_disconnect_takes_the_sender_into_account(signal):
    calls = []

    def receiver(sender, instance):
        calls.append(sender)

    signal.connect(receiver, sender=Thing)
    signal.connect(receiver, sender=Other)
    signal.disconnect(receiver, sender=Thing)
    signal.send(Thing())
    signal.send(Other())
    assert calls == [Other]


def test_disconnecting_an_unknown_receiver_fails(signal):
    def receiver(sender, instance):
        pass

    with pytest.raises(ValueError, match="sender=any not found"):
        signal.disconnect(receiver)

    signal.connect(receiver)
    with pytest.raises(ValueError, match="not found"):
        signal.disconnect(receiver, sender=Thing)


def test_a_receiver_connected_while_sending_waits_for_the_next_send(signal):
    calls = []

    def late(sender, instance):
        calls.append("late")

    def receiver(sender, instance):
        calls.append("first")
        signal.connect(late)

    signal.connect(receiver)
    signal.send(Thing())
    assert calls == ["first"]


def test_an_error_in_a_receiver_stops_the_ones_after_it(signal):
    calls = []

    def broken(sender, instance):
        raise RuntimeError("nope")

    signal.connect(broken)
    signal.connect(lambda sender, instance: calls.append("after"))
    with pytest.raises(RuntimeError, match="nope"):
        signal.send(Thing())
    assert calls == []


# --- threads ---


def _run_in_threads(count, target):
    barrier = threading.Barrier(count)

    def run(index):
        barrier.wait()
        target(index)

    threads = [threading.Thread(target=run, args=(i,)) for i in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()


def test_receivers_connected_from_many_threads_are_all_kept(signal):
    receivers = [lambda sender, instance, i=i: i for i in range(200)]

    def connect(index):
        for receiver in receivers[index::8]:
            signal.connect(receiver)

    _run_in_threads(8, connect)

    assert len(signal._receiver_list) == 200
    assert sorted(value for _, value in signal.send(Thing())) == list(range(200))


def test_only_one_thread_connects_the_same_receiver(signal):
    def receiver(sender, instance):
        pass

    errors = []

    def connect(index):
        try:
            signal.connect(receiver)
        except ValueError:
            errors.append(index)

    _run_in_threads(8, connect)

    assert len(errors) == 7
    assert len(signal.send(Thing())) == 1


def test_connect_and_disconnect_from_many_threads(signal):
    def connect_and_disconnect(index):
        for _ in range(100):
            def receiver(sender, instance):
                pass

            signal.connect(receiver)
            signal.send(Thing())
            signal.disconnect(receiver)

    _run_in_threads(8, connect_and_disconnect)

    assert signal._receiver_list == []
    assert signal._receivers == frozenset()


# --- decorator ---


def test_decorating_a_module_function_connects_it_for_every_sender():
    assert module_receiver(Thing, Thing()) == "module"
    assert module_signal.send(Thing()) == [(module_receiver, "module")]
    assert module_signal.send(Other()) == [(module_receiver, "module")]


def test_decorating_a_nested_function_connects_it_for_every_sender(signal):
    @signal
    def receiver(sender, instance):
        return sender

    assert signal.send(Thing()) == [(receiver, Thing)]
    assert signal.send(Other()) == [(receiver, Other)]


def test_decorating_a_method_connects_it_for_its_class(signal):
    calls = []

    class Doc:
        @signal
        def on_signal(self, *args, **kwargs):
            calls.append((self, args, kwargs))
            return "method"

    class Unrelated:
        pass

    doc = Doc()
    responses = signal.send(doc, 1, flag=True)

    assert calls == [(doc, (1,), {"flag": True})]
    assert responses == [(Doc.on_signal, "method")]
    assert signal.send(Unrelated()) == []


def test_a_decorated_method_stays_a_plain_method(signal):
    class Doc:
        @signal
        def on_signal(self):
            return "method"

    assert Doc().on_signal() == "method"
    assert Doc.on_signal.__name__ == "on_signal"
    assert not isinstance(Doc.__dict__["on_signal"], signals._MethodReceiver)


def test_a_decorated_method_can_be_disconnected(signal):
    class Doc:
        @signal
        def on_signal(self):
            return "method"

    signal.disconnect(Doc.on_signal, sender=Doc)
    assert signal.send(Doc()) == []


def test_a_decorated_method_runs_for_subclasses(signal):
    calls = []

    class Doc:
        @signal
        def on_signal(self):
            calls.append(type(self).__name__)

    class Report(Doc):
        pass

    signal.send(Report())
    assert calls == ["Report"]


def test_a_subclass_can_override_a_decorated_method(signal):
    calls = []

    class Doc:
        @signal
        def on_signal(self):
            calls.append("doc")

    class Report(Doc):
        def on_signal(self):
            calls.append("report")

    signal.send(Report())
    assert calls == ["report"]

    signal.send(Doc())
    assert calls == ["report", "doc"]


def test_an_override_decorated_again_runs_once(signal):
    calls = []

    class Doc:
        @signal
        def on_signal(self):
            calls.append("doc")

    class Report(Doc):
        @signal
        def on_signal(self):
            calls.append("report")

    responses = signal.send(Report())
    assert calls == ["report"]
    assert responses == [(Report.on_signal, None)]


def test_an_override_can_call_the_parent(signal):
    calls = []

    class Doc:
        @signal
        def on_signal(self):
            calls.append("doc")

    class Report(Doc):
        def on_signal(self):
            super().on_signal()
            calls.append("report")

    signal.send(Report())
    assert calls == ["doc", "report"]


def test_several_decorated_methods_run_in_the_order_they_were_defined(signal):
    calls = []

    class Doc:
        @signal
        def first(self):
            calls.append("first")

        @signal
        def second(self):
            calls.append("second")

    signal.send(Doc())
    assert calls == ["first", "second"]


def test_a_method_can_be_decorated_with_several_signals():
    one = ModelSignal()
    two = ModelSignal()
    three = ModelSignal()
    calls = []

    class Doc:
        @one
        @two
        @three
        def on_signal(self):
            calls.append("called")

    doc = Doc()
    assert doc.on_signal.__name__ == "on_signal"
    for signal in (one, two, three):
        assert signal.send(doc) == [(Doc.on_signal, None)]
    assert calls == ["called", "called", "called"]


def test_a_method_connected_by_hand(signal):
    def on_signal(self):
        return type(self).__name__

    signal.connect(on_signal, sender=Thing, is_method=True)
    assert signal.send(SubThing()) == [(on_signal, "SubThing")]


def test_a_method_receiver_gets_the_class_when_a_class_is_sent(signal):
    class Doc:
        @signal
        def on_signal(self):
            return self

    assert signal.send(Doc) == [(Doc.on_signal, Doc)]


# --- models ---


def test_create_fires_the_save_and_the_create_signals(Book, log):
    Book.create(title="A")
    assert log == ["before_save", "before_create", "after_create", "after_save"]


def test_saving_a_new_instance_fires_the_save_and_the_create_signals(Book, log):
    Book(title="A").save()
    assert log == ["before_save", "before_create", "after_create", "after_save"]


def test_saving_an_existing_instance_fires_only_the_save_signals(Book, log):
    book = Book.create(title="A")
    log.clear()
    book.title = "B"
    book.save()
    assert log == ["before_save", "after_save"]


def test_force_insert_fires_the_create_signals(Book, log):
    Book(id=7, title="A").save(force_insert=True)
    assert log == ["before_save", "before_create", "after_create", "after_save"]
    assert Book.find(7).title == "A"


def test_an_instance_with_a_primary_key_is_an_update(db, BaseModel, log):
    class Country(BaseModel):
        code = pw.CharField(primary_key=True)
        name = pw.CharField(default="")

    db.create_tables([Country])

    # Without `force_insert`, Peewee updates the row with that key
    assert Country(code="cl", name="Chile").save() == 0
    assert log == ["before_save", "after_save"]
    assert Country.select().count() == 0

    log.clear()
    Country.create(code="cl", name="Chile")
    assert log == ["before_save", "before_create", "after_create", "after_save"]


def test_a_primary_key_of_zero_is_an_update(Book, log):
    Book(id=0, title="A").save()
    assert log == ["before_save", "after_save"]
    assert Book.select().count() == 0


def test_a_model_without_primary_key_is_always_created(db, BaseModel, log):
    class Visit(BaseModel):
        path = pw.CharField()

        class Meta:
            primary_key = False

    db.create_tables([Visit])

    Visit.create(path="/a")
    assert log == ["before_save", "before_create", "after_create", "after_save"]

    log.clear()
    visit = Visit(path="/b")
    visit.save()
    visit.save()
    assert log == ["before_save", "before_create", "after_create", "after_save"] * 2
    assert Visit.select().count() == 3


def test_delete_instance_fires_the_delete_signals(Book, log):
    book = Book.create(title="A")
    log.clear()
    book.delete_instance()
    assert log == ["before_delete", "after_delete"]


def test_receivers_get_the_model_and_the_instance(Book):
    calls = []
    for model_signal in MODEL_SIGNALS.values():
        model_signal.connect(lambda sender, instance: calls.append((sender, instance)))

    book = Book.create(title="A")
    book.delete_instance()

    assert calls == [(Book, book)] * 6


def test_the_row_exists_after_the_create_but_not_before(Book):
    seen = {}

    @before_create
    def before(sender, instance):
        seen["before"] = (instance.id, Book.select().count())

    @after_create
    def after(sender, instance):
        seen["after"] = (instance.id, Book.select().count())

    Book.create(title="A")
    assert seen == {"before": (None, 0), "after": (1, 1)}


def test_the_row_exists_before_the_delete_but_not_after(Book):
    seen = {}

    @before_delete
    def before(sender, instance):
        seen["before"] = Book.select().count()

    @after_delete
    def after(sender, instance):
        seen["after"] = Book.select().count()

    Book.create(title="A").delete_instance()
    assert seen == {"before": 1, "after": 0}


def test_a_before_receiver_can_change_what_is_saved(Book):
    @before_save
    def upper(sender, instance):
        instance.title = instance.title.upper()

    book = Book.create(title="a")
    assert Book.find(book.id).title == "A"

    book.title = "b"
    book.save()
    assert Book.find(book.id).title == "B"


def test_save_and_delete_instance_return_what_peewee_returns(Book):
    book = Book(title="A")
    assert book.save() == 1
    book.title = "B"
    assert book.save(only=[Book.title]) == 1
    assert Book.find(book.id).title == "B"
    assert book.delete_instance() == 1


def test_the_signals_fire_even_if_there_is_nothing_to_save(db, BaseModel, log):
    class Draft(BaseModel):
        title = pw.CharField()

        class Meta:
            only_save_dirty = True

    db.create_tables([Draft])
    draft = Draft.create(title="A")
    log.clear()

    assert draft.save() is False
    assert log == ["before_save", "after_save"]


def test_delete_instance_passes_its_arguments(db, BaseModel, log):
    class Author(BaseModel):
        name = pw.CharField()

    class Post(BaseModel):
        author = pw.ForeignKeyField(Author, backref="posts")

    db.create_tables([Author, Post])
    author = Author.create(name="A")
    Post.create(author=author)
    Post.create(author=author)
    log.clear()

    author.delete_instance(recursive=True)

    assert Post.select().count() == 0
    # The posts are deleted with a query, so only the author fires signals
    assert log == ["before_delete", "after_delete"]


def test_bulk_operations_do_not_fire_signals(Book, log):
    Book.insert(title="A").execute()
    Book.insert_many([{"title": "B"}, {"title": "C"}]).execute()
    Book.update(title="Z").where(Book.title == "A").execute()
    Book.delete().where(Book.title == "B").execute()
    assert log == []
    assert Book.select().count() == 2


@pytest.mark.parametrize("name", ["before_save", "before_create"])
def test_an_error_before_creating_stops_it(Book, name):
    @MODEL_SIGNALS[name]
    def broken(sender, instance):
        raise RuntimeError("nope")

    with pytest.raises(RuntimeError, match="nope"):
        Book.create(title="A")
    assert Book.select().count() == 0


@pytest.mark.parametrize("name", ["after_create", "after_save"])
def test_an_error_after_creating_keeps_the_row(Book, name):
    @MODEL_SIGNALS[name]
    def broken(sender, instance):
        raise RuntimeError("nope")

    with pytest.raises(RuntimeError, match="nope"):
        Book.create(title="A")
    assert Book.select().count() == 1


def test_an_error_before_saving_stops_the_update(Book):
    book = Book.create(title="A")

    @before_save
    def broken(sender, instance):
        raise RuntimeError("nope")

    book.title = "B"
    with pytest.raises(RuntimeError, match="nope"):
        book.save()
    assert Book.find(book.id).title == "A"


def test_an_error_before_deleting_stops_it(Book):
    book = Book.create(title="A")

    @before_delete
    def broken(sender, instance):
        raise RuntimeError("nope")

    with pytest.raises(RuntimeError, match="nope"):
        book.delete_instance()
    assert Book.select().count() == 1


def test_an_error_after_deleting_keeps_the_row_deleted(Book):
    book = Book.create(title="A")

    @after_delete
    def broken(sender, instance):
        raise RuntimeError("nope")

    with pytest.raises(RuntimeError, match="nope"):
        book.delete_instance()
    assert Book.select().count() == 0


def test_an_error_after_creating_is_rolled_back_by_a_transaction(db, Book):
    @after_create
    def broken(sender, instance):
        raise RuntimeError("nope")

    with pytest.raises(RuntimeError, match="nope"), db.atomic():
        Book.create(title="A")
    assert Book.select().count() == 0


def test_methods_of_a_model_as_receivers(db, BaseModel):
    calls = []

    class Article(BaseModel):
        title = pw.CharField()
        slug = pw.CharField(default="")

        @before_save
        def set_slug(self):
            self.slug = self.title.lower().replace(" ", "-")

        @after_create
        def created(self):
            calls.append(("created", self.id))

        @after_save
        def saved(self):
            calls.append(("saved", self.id))

        @before_delete
        def deleting(self):
            calls.append(("deleting", self.id))

    class Note(BaseModel):
        text = pw.CharField()

    db.create_tables([Article, Note])

    article = Article.create(title="Hello World")
    assert article.slug == "hello-world"
    assert calls == [("created", 1), ("saved", 1)]

    article.title = "Bye"
    article.save()
    assert Article.find(1).slug == "bye"
    assert calls == [("created", 1), ("saved", 1), ("saved", 1)]

    article.delete_instance()
    assert calls[-1] == ("deleting", 1)

    # The receivers of a model are not called for the other models
    calls.clear()
    Note.create(text="hi").delete_instance()
    assert calls == []


def test_a_method_decorated_for_create_and_delete(db, BaseModel):
    calls = []

    class Entry(BaseModel):
        name = pw.CharField()

        @after_create
        @after_delete
        def changed(self):
            calls.append(self.name)

    db.create_tables([Entry])
    entry = Entry.create(name="a")
    entry.name = "b"
    entry.save()
    entry.delete_instance()
    assert calls == ["a", "b"]


def test_receivers_of_a_table_less_parent_run_for_its_models(db, BaseModel):
    calls = []

    class Tracked(BaseModel):
        @after_create
        def track(self):
            calls.append(type(self).__name__)

    class Invoice(Tracked):
        number = pw.IntegerField()

    class Refund(Tracked):
        number = pw.IntegerField()

        def track(self):
            calls.append("refund, overridden")

    class Plain(BaseModel):
        number = pw.IntegerField()

    db.create_tables([Invoice, Refund, Plain])
    Invoice.create(number=1)
    Refund.create(number=2)
    Plain.create(number=3)
    assert calls == ["Invoice", "refund, overridden"]


def test_a_receiver_for_one_model(db, BaseModel, Book):
    class Magazine(BaseModel):
        title = pw.CharField()

    db.create_tables([Magazine])
    calls = []
    after_create.connect(lambda sender, instance: calls.append(sender), sender=Book)

    Magazine.create(title="M")
    Book.create(title="B")
    assert calls == [Book]
