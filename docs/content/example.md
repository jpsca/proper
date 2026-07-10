

```python {title="myapp/models/article.py"}
import peewee as pw
from proper.rich_text import HasRichText, RichTextField

from .base import BaseModel, scope
from .attachment import Attachment
from .user import User

class Article(BaseModel, HasRichText):
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

```python {title="myapp/controllers/controller_article.py"}
from proper.errors import NotFound

from ..forms.article import ArticleForm
from ..models import Article
from ..router import router
from .app_controller import AppController


@router.resource("articles")
class ArticleController(AppController):
  before = [
    {"do": "set_article", "exclude": ["index", "new", "create"]},
    {"do": "set_form", "exclude": ["index", "show", "delete"]},
    {"do": "validate_form", "only": ["create", "update"]},
  ]

  def index(self):
    self.articles = Article.select().published().recent()

  def show(self):
    if self.article.is_draft:
      raise NotFound

  def new(self): pass

  def edit(self): pass

  def create(self):
    article = self.form.save()
    self.response.redirect_to("Article.show", article,
                  flash="Article was created")

  # Private

  def set_article(self):
    article_id = self.params.get("article_id", "")
    self.article = Article.get_or_none(id=int(article_id))
    if not self.article:
      raise NotFound

  def set_form(self):
    obj = getattr(self, "article", None)
    self.form = ArticleForm(self.params, object=obj)
  
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
