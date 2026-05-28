from proper.rich_text import RichTextDocument


def test_save_and_load_returns_document(PostNoAttachments):
    html = "<p>Hi <strong>there</strong></p>"
    PostNoAttachments.create(body=html)
    post = PostNoAttachments.get()
    assert isinstance(post.body, RichTextDocument)
    assert post.body.to_html() == html


def test_can_assign_a_document(PostNoAttachments):
    doc = RichTextDocument("<p>x</p>")
    PostNoAttachments.create(body=doc)
    post = PostNoAttachments.get()
    assert post.body.to_html() == "<p>x</p>"


def test_null_value_round_trips_as_none(PostNoAttachments):
    PostNoAttachments.create(body=None)
    post = PostNoAttachments.get()
    assert post.body is None


def test_attachment_cls_propagates_to_document(Post):
    Post.create(
        body='<proper-attachment sgid="abc"></proper-attachment>',
    )
    post = Post.get()
    assert post.body._attachment_cls is not None
