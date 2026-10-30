

```python {title="myapp/models/article.py"}
import peewee as pw
from proper.rich_text import HasRichText, RichTextField

from .base import BaseModel, scope
from .attachment import Attachment
from .user import User

class Article(HasRichText, BaseModel):
  title = pw.CharField()
  content = RichTextField(Attachment, null=True)
  cover_image = pw.ForeignKeyField(Attachment, null=True)
  is_draft = pw.BooleanField(default=True)

  author = pw.ForeignKeyField(
    model=User,
    backref="articles",
    default=lambda: current.user
  )

  @scope
  def published(cls, query):
    return query.where(cls.is_draft==False)

  @scope
  def recent(cls, query):
    return (
      query
      .order_by(cls.created_at.desc())
      .limit(25)
    )
  
  def byline(self):
    return (
       f"Written by {self.author.name} "
       f"on {self.created_at.strftime('%b %d, %Y')}"
    )
  
  def publish(self):
    self.is_draft = False

```

```python {title="myapp/controllers/article_controller.py"}
from proper.errors import NotFound

from ..forms.article import ArticleForm
from ..models import Article
from ..router import router
from .app_controller import AppController


@router.resource("articles")
class ArticleController(AppController):

  def index(self):
    self.articles = Article.select().published().recent()

  def show(self):
    self.load_article()
    if not self.article or self.article.is_draft:
      raise NotFound

  def new(self):
    self.form = ArticleForm(self.params)

  def edit(self):
    self.load_article()
    if not self.article:
      raise NotFound

    self.form = ArticleForm(self.params, self.article)

  def create(self):
    self.form = ArticleForm(self.params)
    if self.form.is_invalid:
      return self.redo()
    article = self.form.save()
    self.response.redirect_to("Article.show", article,
                  flash="Article was created")

  # Private

  def load_article(self):
    article_id = self.params.get("article_id", "")
    self.article = Article.find(int(article_id)) if article_id.isdigit() else None
```


```python {title="myapp/forms/article.py"}
from proper import forms as f

from ..models import Article, Attachment

class ArticleForm(f.Form):
  class Meta:
    orm_cls = Article

  title = f.TextField()
  content = f.RichTextField(required=False)
  cover_image = f.AttachmentField(Attachment, required=False)
  is_draft = f.BooleanField(default=False)

```

```html+jinja {title="myapp/views/article/show.jx"}
{#import "layouts/app.jx" as Layout #}
{#def article #}

<Layout title="Room">
  <h1>{{ article.title }}</h1>
  <img src="{{ article.cover_image.url }}" alt="{{ article.title }}">
  <p>{{ article.content }}</p>

  {% if current.user.is_admin -%}
  <a href="{{ url_for('Article.edit', article) }}">Edit</a>
  {% endif %}
</Layout>
```
