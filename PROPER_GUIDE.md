# Guía Completa del Framework Proper

## Tabla de Contenidos

1. [Introducción](#introducción)
2. [Principios de Diseño](#principios-de-diseño)
3. [Arquitectura General](#arquitectura-general)
4. [Instalación y Configuración](#instalación-y-configuración)
5. [Estructura de un Proyecto](#estructura-de-un-proyecto)
6. [Conceptos Fundamentales](#conceptos-fundamentales)
7. [Routing (Enrutamiento)](#routing-enrutamiento)
8. [Controllers (Controladores)](#controllers-controladores)
9. [Request y Response](#request-y-response)
10. [Vistas y Templates](#vistas-y-templates)
11. [Concerns (Mixins de Comportamiento)](#concerns-mixins-de-comportamiento)
12. [Modelos y Base de Datos](#modelos-y-base-de-datos)
13. [Autenticación](#autenticación)
14. [Cache](#cache)
15. [Queue (Colas de Trabajo)](#queue-colas-de-trabajo)
16. [Storage (Almacenamiento de Archivos)](#storage-almacenamiento-de-archivos)
17. [Email](#email)
18. [Internacionalización (i18n)](#internacionalización-i18n)
19. [Deployment](#deployment)
20. [CLI (Command Line Interface)](#cli-command-line-interface)

---

## Introducción

**Proper** es un framework web para Python inspirado en **Phoenix (Elixir)** y **Ruby on Rails**, optimizado para la felicidad del programador. Utiliza WSGI y sigue el principio de "Convention over Configuration".

## Arquitectura General

```
┌─────────────────┐
│   WSGI Server   │ (Gunicorn, uWSGI, etc.)
└────────┬────────┘
         │
         ▼
    ┌────────┐
    │  App   │ ← Punto de entrada principal
    └────┬───┘
         │
         ├──► Router      ← Mapea URLs a controllers
         ├──► Request     ← Encapsula la petición HTTP
         ├──► Response    ← Encapsula la respuesta HTTP
         ├──► Tools       ← db, cache, queue, auth, etc.
         └──► Catalog     ← Motor de templates (Jinja2)
              │
              ├──► Pipeline  ← Procesa la petición en etapas
              │
              └──► Controllers ← Lógica de negocio
                   │
                   ├──► Concerns ← Comportamientos reutilizables
                   └──► Views    ← Templates Jinja2
```

### Pipeline de Procesamiento

Cada petición pasa por estas etapas:

1. **head_to_get**: Convierte HEAD a GET
2. **method_override**: Permite sobrescribir método HTTP
3. **match**: Busca la ruta coincidente
4. **redirect**: Maneja redirecciones
5. **dispatch**: Ejecuta el controller
6. **strip_body_if_head**: Elimina body si es HEAD

---

## Instalación y Configuración

### Instalación

```bash
pip install proper
```

### Crear un Nuevo Proyecto

```bash
proper new myapp
cd myapp
```

### Estructura Generada

```
myapp/
├── myapp/                  # Código de la aplicación
│   ├── __init__.py
│   ├── main.py            # Instancia de App
│   ├── setup.py           # Setup de la aplicación
│   ├── router.py          # Rutas
│   ├── config/            # Configuración
│   ├── controllers/       # Controllers
│   ├── models/            # Modelos
│   ├── views/             # Templates Jx
│   ├── mailers/           # Mailers
│   ├── tasks/             # Tareas en cola
│   └── cl/                # Comandos CLI
├── static/                # Archivos estáticos
├── storage/               # Almacenamiento de archivos
├── db/                    # Migraciones de base de datos
├── tests/                 # Tests
├── pyproject.toml         # Dependencias
└── gunicorn.py           # Config de Gunicorn
```

---

## Estructura de un Proyecto

### main.py - El Núcleo de la Aplicación

```python
from proper import App
from . import config

app = App(__name__, config)
config = app.config
auth = app.auth  # Si usas autenticación
```

### __init__.py - Orden de Importación

```python
from . import main     # noqa
from . import setup    # noqa - Setup de la app
from . import router   # noqa - Define rutas
from . import controllers  # noqa - Monta controllers
from . import models   # noqa
from . import tasks    # noqa
```

**Importante**: El orden de importación importa. `setup.py` debe ir antes de `router.py`, y `router.py` antes de `controllers`.

### config/__init__.py - Configuración

```python
class Config:
    DEBUG = False

    # Seguridad
    SECRET_KEYS = ["your-secret-key-here"]

    # Base de datos
    DATABASES = {
        "main": {
            "type": "playhouse.sqlite_ext.SqliteExtDatabase",
            "database": "db/main.db",
        }
    }

    # Cache
    CACHE = {
        "type": "proper.cache.NoCache",
    }

    # Queue
    QUEUE = {
        "type": "huey.MemoryHuey",
        "immediate": True,
    }

    # Session
    SESSION_COOKIE_LIFETIME = 60 * 60 * 24 * 7  # 7 días
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # Static files
    ASSETS_URL = "/static/"

    # Auth
    AUTH_PASSWORD_MINLEN = 9
    AUTH_TOKEN_LIFE = 3 * 60 * 60  # 3 horas

class Development(Config):
    DEBUG = True

class Production(Config):
    # Override para producción
    pass
```

---

## Conceptos Fundamentales

### App - La Aplicación Principal

`App` es el núcleo del framework. Se instancia una vez y coordina todos los componentes:

```python
from proper import App

app = App(__name__, config)

# Propiedades importantes:
app.router      # Router de la aplicación
app.config      # Configuración
app.db          # Dict de bases de datos
app.cache       # Sistema de cache
app.queue       # Cola de trabajos
app.auth        # Sistema de autenticación
app.mailer      # Sistema de email
app.storage     # Almacenamiento de archivos
app.i18n        # Internacionalización (si está instalado)
```

### Global Context (g)

Proper proporciona un contexto global **thread-safe** para la petición actual:

```python
from proper import g

# En cualquier parte del código durante una petición:
g.app         # La instancia de App
g.request     # La petición actual
g.response    # La respuesta actual

# Puedes añadir tus propios datos:
g.current_user = user
```

---

## Routing (Enrutamiento)

El router mapea URLs a métodos de controllers.

### Rutas Básicas

```python
# router.py
from .main import app
router = app.router

# Importar controllers
from .controllers import public

# Las rutas se definen como decoradores en los controllers:
# @router.get("/")
```

### Decoradores de Ruta

```python
from .router import router
from .base import BaseController

class PublicController(BaseController):
    # GET /
    @router.get("/")
    def index(self):
        return self.render("pages/index.jinja")

    # POST /contact
    @router.post("/contact")
    def contact(self):
        # ...
        pass

    # GET /posts/:id
    @router.get("/posts/:id")
    def show_post(self):
        post_id = self.params.get("id")
        # ...
        pass

    # PUT /posts/:id
    @router.put("/posts/:id")
    def update_post(self):
        # ...
        pass

    # DELETE /posts/:id
    @router.delete("/posts/:id")
    def delete_post(self):
        # ...
        pass
```

### Parámetros en Rutas

```python
# Parámetros básicos
@router.get("/users/:user_id")  # Cualquier valor excepto /

# Parámetros con tipo
@router.get("/posts/:year<int>/:month<int>/:day<int>/:slug")

# Parámetros con regex
@router.get("/docs/:lang<en|es|pt>")

# Capturar todo el path (incluyendo /)
@router.get("/files/:path<path>")

# Acceder a los parámetros:
def show_user(self):
    user_id = self.params.get("user_id")
```

### Recursos RESTful

Proper tiene soporte nativo para recursos REST:

```python
@router.resource("/posts")
class PostController(BaseController):
    # GET /posts
    def index(self):
        posts = Post.select()
        return self.render("posts/index.jinja", posts=posts)

    # GET /posts/new
    def new(self):
        return self.render("posts/new.jinja")

    # POST /posts
    def create(self):
        # Crear post
        pass

    # GET /posts/:pk
    def show(self):
        pk = self.params.get("pk")
        post = Post.get_by_id(pk)
        return self.render("posts/show.jinja", post=post)

    # GET /posts/:pk/edit
    def edit(self):
        pk = self.params.get("pk")
        post = Post.get_by_id(pk)
        return self.render("posts/edit.jinja", post=post)

    # PUT/PATCH /posts/:pk
    def update(self):
        # Actualizar post
        pass

    # DELETE /posts/:pk
    def delete(self):
        # Eliminar post
        pass

    # RESTORE /posts/:pk (no estándar, pero útil)
    def restore(self):
        # Restaurar post eliminado
        pass
```

### Recurso Singular

Para recursos que no necesitan ID (como un perfil de usuario):

```python
@router.resource("/profile", singular=True)
class ProfileController(BaseController):
    # GET /profile
    def show(self):
        pass

    # GET /profile/new
    def new(self):
        pass

    # POST /profile
    def create(self):
        pass

    # GET /profile/edit
    def edit(self):
        pass

    # PATCH/PUT /profile
    def update(self):
        pass
```

### Scopes (Agrupación de Rutas)

```python
# Agrupar rutas con un prefijo
api = router.scope("/api/v1")

class ApiController(BaseController):
    # GET /api/v1/users
    @api.get("/users")
    def list_users(self):
        pass

    # POST /api/v1/users
    @api.post("/users")
    def create_user(self):
        pass
```

### Host-based Routing

```python
# Rutas específicas para un host
@router.get("/", host="admin.example.com")
def admin_index(self):
    pass

@router.get("/", host=":subdomain.example.com")
def subdomain_index(self):
    subdomain = self.params.get("subdomain")
```

### Archivos Estáticos

```python
# En router.py
router.static(
    app.config.ASSETS_URL,  # "/static/"
    root=app.static_path,
    name="static"
)
```

### Redirecciones

```python
# Redirección simple
router.get("/old-path", redirect="/new-path")

# En un controller:
def some_action(self):
    self.response.redirect_to("/another-path")
    # O usando una ruta nombrada:
    self.response.redirect_to("Post.show", pk=123)
```

### Nombrar Rutas y url_for()

```python
# Dar nombre a una ruta
@router.get("/about", name="about_page")
def about(self):
    pass

# Generar URLs en controllers:
url = self.app.url_for("about_page")
url = self.app.url_for("Post.show", pk=123)

# En templates:
{{ url_for("about_page") }}
{{ url_for("Post.show", pk=post.id) }}
```

### Manejadores de Errores

```python
from proper import errors

class PublicController(BaseController):
    @router.error(errors.NotFound)
    @router.get("_not_found")  # URL para preview en debug
    def not_found(self):
        return self.render("pages/not-found.jinja")

    @router.error(Exception)
    @router.get("_error")
    def error(self):
        return self.render("pages/error.jinja")
```

---

## Controllers (Controladores)

Los controllers contienen la lógica de negocio de tu aplicación.

### Estructura Básica

```python
from proper import Controller

class MyController(Controller):
    def __init__(self, app, request, response):
        super().__init__(app, request, response)
        # self.app - La aplicación
        # self.request - La petición
        # self.response - La respuesta

    def some_action(self):
        # Lógica aquí
        return self.render("template.jinja")
```

### BaseController

Es buena práctica tener un `BaseController` del que heredan todos los demás:

```python
# controllers/base.py
from proper import Controller
from proper.concerns import (
    RequestForgeryProtection,
    RestoreSession,
    UpdateSessionCookie,
)

class BaseController(Controller):
    """Todos los controllers heredan de esta clase."""

    # Concerns que se ejecutan antes de la acción
    before = [
        RestoreSession(),
        RequestForgeryProtection(),
    ]

    # Concerns que se ejecutan después de la acción
    after = [
        UpdateSessionCookie(),
    ]
```

### Propiedades Importantes

```python
class MyController(BaseController):
    def index(self):
        # Acceso a la aplicación
        cache = self.app.cache

        # Acceso a la petición
        user = self.request.user
        path = self.request.path

        # Acceso a la respuesta
        self.response.status = "200 OK"

        # Parámetros combinados (query + form + route params)
        name = self.params.get("name")

        # Valores por defecto de la ruta
        controller_name = self.defaults.get("controller")
```

### render() - Renderizar Templates

```python
def index(self):
    posts = Post.select()

    # Renderizar template con variables
    return self.render("posts/index.jinja", posts=posts)

    # Cambiar status
    return self.render("posts/show.jinja", status="404 Not Found")

    # Retornar JSON
    return self.render(json={"posts": [...]})

    # Retornar texto plano
    return self.render(text="Hello, World!")
```

### Variables de Instancia para Templates

Las variables de instancia del controller están disponibles en el template:

```python
def show(self):
    self.post = Post.get_by_id(123)
    self.author = self.post.author
    return self.render("posts/show.jinja")

# En el template:
# {{ post.title }}
# {{ author.name }}
```

### Concerns (Callbacks)

Los concerns son comportamientos reutilizables que se ejecutan antes o después de las acciones:

```python
class MyController(BaseController):
    before = [
        RestoreSession(),        # Restaura la sesión
        RestoreUser(),          # Restaura el usuario logueado
        RequireLogin(),         # Requiere login
        RequestForgeryProtection(),  # CSRF
    ]

    after = [
        UpdateSessionCookie(),  # Actualiza la cookie de sesión
        SetSecurityHeaders(),   # Agrega headers de seguridad
    ]
```

Los concerns pueden retornar una respuesta temprana:

```python
class RequireLogin:
    def __call__(self, co):
        if not co.request.user:
            co.response.redirect_to("Session.new")
            return co.response  # Retorna respuesta, detiene ejecución
```

### Controller Privado (Solo Usuarios Logueados)

```python
from .concerns.require_login import RequireLogin
from .concerns.restore_user import RestoreUser

class PrivateController(BaseController):
    before = [
        RestoreSession(),
        RestoreUser(),
        RequireLogin(),  # Requiere que el usuario esté logueado
        RequestForgeryProtection(),
    ]
```

---

## Request y Response

### Request

El objeto `Request` encapsula toda la información de la petición HTTP:

```python
def my_action(self):
    req = self.request

    # Método HTTP
    req.method  # "GET", "POST", etc.
    req.is_get, req.is_post, req.is_put, req.is_delete

    # URL y componentes
    req.url         # URL completa
    req.path        # "/posts/123"
    req.query_string  # "page=2&sort=date"
    req.host        # "example.com"
    req.port        # 80
    req.protocol    # "https"

    # Parámetros de query string
    page = req.query.get("page")
    tags = req.query.getlist("tags")  # Para múltiples valores

    # Datos del formulario (POST)
    name = req.form.get("name")
    files = req.form.getlist("photos")

    # Headers
    req.content_type
    req.accept
    req.accept_language
    req.user_agent

    # Cookies
    session_id = req.cookies.get("session_id")

    # Usuario (si está autenticado)
    user = req.user

    # Sesión
    user_id = req.session.get("user_id")

    # CSRF Token
    token = req.csrf_token

    # Locale/idioma
    locale = req.locale  # "es_ES"
    lang = req.language  # "es"

    # IP del cliente
    ip = req.remote_ip

    # Request ID único
    req_id = req.request_id

    # Es HTTPS?
    req.is_secure

    # Es AJAX?
    req.is_xhr

    # Flashes (mensajes flash)
    messages = req.flashes
```

### Response

El objeto `Response` encapsula la respuesta HTTP:

```python
def my_action(self):
    resp = self.response

    # Status
    resp.status = "404 Not Found"
    resp.status = status.not_found  # Importado de proper.status

    # Body
    resp.body = "<h1>Hello</h1>"
    resp.body = b"Binary data"

    # Headers
    resp.headers["X-Custom"] = "value"
    resp.set_content_type("application/json")

    # Cookies
    resp.set_cookie("name", "value")
    resp.set_signed_cookie("token", {"user_id": 123})
    resp.unset_cookie("name")

    # Cache headers
    resp.set_cache_control("max-age=3600", "public")
    resp.set_etag("abc123")
    resp.set_last_modified(datetime.now())

    # Redirección
    resp.redirect_to("/new-path")
    resp.redirect_to("Post.show", pk=123)
    resp.redirect_to("/login", flash="Please log in", flash_type="warning")

    # Enviar archivos
    resp.send_file("/path/to/file.pdf")
    resp.send_file("/path/to/file.pdf", as_attachment=True, download_name="doc.pdf")

    # Flash messages
    resp.flash.info("Operation successful")
    resp.flash.warning("Warning message")
    resp.flash.error("Error message")
    resp.flash.success("Success!")

    # Sesión
    resp.session["user_id"] = 123
    resp.session["preferences"] = {"theme": "dark"}

    # Freshness (caching)
    if resp.fresh_when(objects=posts):
        # No es necesario renderizar, envía 304 Not Modified
        return
```

---

## Vistas y Templates

Proper usa **Jinja2** como motor de templates.

### Estructura de Directorios

```
myapp/views/
├── layouts/           # Layouts base
│   ├── app.jinja
│   ├── public.jinja
│   └── email.jinja
├── pages/            # Páginas
│   ├── index.jinja
│   ├── not-found.jinja
│   └── error.jinja
├── posts/            # Templates de posts
│   ├── index.jinja
│   ├── show.jinja
│   ├── edit.jinja
│   └── _form.jinja   # Parcial
├── common/           # Componentes comunes
│   ├── nav.jinja
│   └── flashes.jinja
└── form.jinja        # Helpers de formularios
```

### Layout Base

```jinja
{# layouts/app.jinja #}
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>{% block title %}My App{% endblock %}</title>
    <link rel="stylesheet" href="{{ url_for('static', file='styles/app.css') }}">
    {% block head %}{% endblock %}
</head>
<body>
    {% include "common/nav.jinja" %}

    {% include "common/flashes.jinja" %}

    <main>
        {% block content %}{% endblock %}
    </main>

    <script src="{{ url_for('static', file='js/app.js') }}"></script>
    {% block scripts %}{% endblock %}
</body>
</html>
```

### Template de Página

```jinja
{# posts/show.jinja #}
{% extends "layouts/app.jinja" %}

{% block title %}{{ post.title }} - Blog{% endblock %}

{% block content %}
<article>
    <h1>{{ post.title }}</h1>
    <p class="meta">
        Por {{ post.author.name }} el {{ post.created_at|format_date }}
    </p>

    <div class="content">
        {{ post.content|safe }}
    </div>

    <a href="{{ url_for('Post.edit', pk=post.id) }}">Editar</a>
</article>
{% endblock %}
```

### Variables Disponibles en Templates

```jinja
{# Siempre disponibles: #}
{{ app }}         {# La instancia de App #}
{{ request }}     {# Request actual #}
{{ response }}    {# Response actual #}

{# Funciones globales: #}
{{ url_for('Post.show', pk=123) }}
{{ url_is('Post.index') }}        {# True si estamos en esa ruta #}
{{ url_startswith('Post') }}      {# True si la ruta empieza así #}

{# Variables del controller: #}
{{ post }}        {# self.post en el controller #}
{{ posts }}       {# self.posts en el controller #}

{# Si i18n está instalado: #}
{{ _("Hello") }}  {# Traducción #}
```

### Filtros i18n (si está instalado)

```jinja
{{ date|format_date }}
{{ date|format_datetime }}
{{ date|format_time }}
{{ number|format_decimal }}
{{ price|format_currency(currency='USD') }}
{{ percentage|format_percent }}
```

### Fragment Caching

Cachear partes del template:

```jinja
{% cache "sidebar", timeout=3600 %}
    <aside>
        {# Contenido que se cachea #}
    </aside>
{% endcache %}

{# Con clave dinámica: #}
{% cache "post-" ~ post.id, timeout=3600 %}
    <article>{{ post.content }}</article>
{% endcache %}
```

---

## Concerns (Mixins de Comportamiento)

Los concerns son clases que implementan comportamientos reutilizables para controllers.

### Concerns Incluidos

#### RestoreSession

Restaura la sesión desde la cookie:

```python
from proper.concerns import RestoreSession

class BaseController(Controller):
    before = [RestoreSession()]
```

#### UpdateSessionCookie

Actualiza la cookie de sesión si cambió:

```python
from proper.concerns import UpdateSessionCookie

class BaseController(Controller):
    after = [UpdateSessionCookie()]
```

#### RequestForgeryProtection

Protección CSRF:

```python
from proper.concerns import RequestForgeryProtection

class BaseController(Controller):
    before = [RequestForgeryProtection()]
```

Saltar verificación para acciones específicas:

```python
before = [
    RequestForgeryProtection(skip_for=["webhook", "api_endpoint"])
]
```

En el template del formulario:

```jinja
<form method="post">
    <input type="hidden" name="csrf_token" value="{{ current.csrf_token }}">
    {# ... #}
</form>
```

### Crear Concerns Personalizados

```python
# controllers/concerns/set_locale.py
class SetLocale:
    def __call__(self, co):
        # co es el controller
        locale = co.request.cookies.get("locale")
        if not locale:
            locale = co.request.accept_language.best_match(["en", "es", "fr"])
        co.request.locale = locale

# Usarlo:
class BaseController(Controller):
    before = [SetLocale()]
```

### Concern que Retorna Respuesta Temprana

```python
class RequireAdmin:
    def __call__(self, co):
        if not co.request.user or not co.request.user.is_admin:
            co.response.redirect_to("home")
            return co.response  # Detiene la ejecución
```

---

## Modelos y Base de Datos

Proper usa **Peewee** como ORM.

### Configuración

```python
# config/__init__.py
DATABASES = {
    "main": {
        "type": "playhouse.sqlite_ext.SqliteExtDatabase",
        "database": "db/main.db",
    },
    # PostgreSQL:
    # "main": {
    #     "type": "peewee.PostgresqlDatabase",
    #     "database": "myapp",
    #     "user": "postgres",
    #     "password": "secret",
    #     "host": "localhost",
    #     "port": 5432,
    # },
}
```

### Acceso a las Bases de Datos

```python
# En un controller:
db = self.app.db["main"]

# En cualquier parte con acceso a g:
from proper import g
db = g.app.db["main"]
```

### Modelo Base

```python
# models/base.py
import peewee as pw
from proper import g

class BaseModel(pw.Model):
    class Meta:
        database = property(lambda self: g.app.db["main"])
        legacy_table_names = False

class TimestampedModel(BaseModel):
    created_at = pw.DateTimeField(default=datetime.now)
    updated_at = pw.DateTimeField(default=datetime.now)

    def save(self, *args, **kwargs):
        self.updated_at = datetime.now()
        return super().save(*args, **kwargs)
```

### Definir Modelos

```python
# models/post.py
import peewee as pw
from .base import TimestampedModel
from .user import User

class Post(TimestampedModel):
    title = pw.CharField(max_length=200)
    slug = pw.CharField(max_length=200, unique=True)
    content = pw.TextField()
    author = pw.ForeignKeyField(User, backref="posts")
    published = pw.BooleanField(default=False)

    class Meta:
        indexes = (
            (("slug",), True),  # Índice único
        )

    @classmethod
    def get_by_slug(cls, slug):
        try:
            return cls.get(cls.slug == slug)
        except cls.DoesNotExist:
            return None
```

### Usar Modelos

```python
# Crear
post = Post.create(
    title="Hello World",
    slug="hello-world",
    content="...",
    author=user
)

# Leer
post = Post.get_by_id(123)
post = Post.get(Post.slug == "hello-world")

# Listar
posts = Post.select().where(Post.published == True).order_by(Post.created_at.desc())

# Actualizar
post.title = "New Title"
post.save()

# O:
Post.update(title="New Title").where(Post.id == 123).execute()

# Eliminar
post.delete_instance()

# O:
Post.delete().where(Post.id == 123).execute()
```

### Migraciones

Proper usa `peewee-migrate`:

```bash
# Crear una migración
proper db create nombre_de_migracion

# Aplicar migraciones
proper db migrate

# Rollback
proper db rollback

# Estado de migraciones
proper db status
```

Estructura de una migración:

```python
# db/main/002_add_posts.py
def migrate(migrator, database, fake=False, **kwargs):
    migrator.create_table(
        'post',
        (
            ('id', migrator.peewee.AutoField(primary_key=True)),
            ('title', migrator.peewee.CharField(max_length=200)),
            ('content', migrator.peewee.TextField()),
            ('created_at', migrator.peewee.DateTimeField()),
        )
    )

def rollback(migrator, database, fake=False, **kwargs):
    migrator.drop_table('post')
```

---

## Autenticación

Proper incluye un sistema de autenticación completo.

### Instalar Blueprint de Auth

```bash
proper install auth
```

Esto genera:

- `models/user.py` - Modelo de usuario
- `controllers/session.py` - Login/logout
- `controllers/password_reset.py` - Reset de contraseña
- `forms/session.py`, `forms/password_reset.py`
- `mailers/auth.py` - Emails de reset
- Templates de login, reset, etc.
- Concerns: `RestoreUser`, `RequireLogin`

### Modelo User

```python
# models/user.py (generado)
from .concerns.authenticable import Authenticable

class User(Authenticable, TimestampedModel):
    email = pw.CharField(max_length=255, unique=True, index=True)
    password = pw.CharField(max_length=255, null=True)

    @classmethod
    def get_by_login(cls, login):
        """Requerido por Auth"""
        try:
            return cls.get(cls.email == login)
        except cls.DoesNotExist:
            return None
```

### Auth API

```python
# En un controller
auth = self.app.auth

# Hash de contraseña
hashed = auth.hash_password("secret123")

# Verificar contraseña
is_valid = auth.password_is_valid("secret123", hashed)

# Autenticar usuario
user = auth.authenticate(User, login="user@example.com", password="secret123")

# Token de sesión
token = auth.get_session_token(user)

# Token con timestamp (para reset de contraseña, etc.)
token = auth.get_timestamped_token(user)

# Autenticar con token
user = auth.authenticate_session_token(User, token)
user = auth.authenticate_timestamped_token(User, token, token_life=3600)
```

### Session Controller (Login/Logout)

```python
# controllers/session.py (generado y personalizable)
class SessionController(BaseController):
    @router.get("/login")
    def new(self):
        return self.render("pages/session/new.jinja")

    @router.post("/login")
    def create(self):
        form = SessionForm(self.request.form)
        if not form.validate():
            return self.render("pages/session/new.jinja", form=form)

        user = self.app.auth.authenticate(
            User,
            login=form.email.data,
            password=form.password.data
        )

        if not user:
            form.add_error("email", "Invalid email or password")
            return self.render("pages/session/new.jinja", form=form)

        # Guardar en sesión
        token = self.app.auth.get_session_token(user)
        self.response.session["auth_token"] = token

        self.response.redirect_to("home", flash="Welcome back!")

    @router.delete("/logout")
    def delete(self):
        self.response.session.clear()
        self.response.redirect_to("home", flash="Logged out")
```

### RestoreUser Concern

```python
# controllers/concerns/restore_user.py (generado)
class RestoreUser:
    def __call__(self, co):
        token = co.request.session.get("auth_token")
        if not token:
            return

        user = co.app.auth.authenticate_session_token(User, token)
        if user:
            co.request.user = user
```

### RequireLogin Concern

```python
# controllers/concerns/require_login.py (generado)
class RequireLogin:
    def __call__(self, co):
        if not co.request.user:
            co.response.redirect_to("Session.new", flash="Please log in")
            return co.response
```

### Usar en Controllers

```python
from .concerns.restore_user import RestoreUser
from .concerns.require_login import RequireLogin

class PrivateController(BaseController):
    before = [
        RestoreSession(),
        RestoreUser(),
        RequireLogin(),  # <-- Requiere login
        RequestForgeryProtection(),
    ]

class DashboardController(PrivateController):
    @router.get("/dashboard")
    def index(self):
        user = self.request.user  # Disponible gracias a RestoreUser
        return self.render("dashboard/index.jinja")
```

---

## Cache

Proper soporta múltiples backends de cache.

### Configuración

```python
# Sin cache (default)
CACHE = {
    "type": "proper.cache.NoCache",
}

# Cache en memoria
CACHE = {
    "type": "proper.cache.MemoryCache",
}

# Cache en Redis
CACHE = {
    "type": "proper.cache.RedisCache",
    "host": "localhost",
    "port": 6379,
    "db": 0,
}

# Cache en SQLite
CACHE = {
    "type": "proper.cache.DatabaseCache",
    "type_db": "playhouse.sqlite_ext.SqliteExtDatabase",
    "database": "db/cache.db",
}
```

### Usar Cache

```python
# En un controller
cache = self.app.cache

# Guardar
cache.set("key", "value", timeout=3600)  # timeout en segundos

# Leer
value = cache.get("key")
value = cache.get("key", default="default_value")

# Eliminar
cache.delete("key")

# Verificar existencia
if cache.has("key"):
    pass

# Limpiar todo
cache.clear()

# Incrementar/decrementar (si el backend lo soporta)
cache.incr("counter")
cache.decr("counter")

# Múltiples valores
cache.set_many({"key1": "val1", "key2": "val2"})
values = cache.get_many(["key1", "key2"])
cache.delete_many(["key1", "key2"])
```

### Decorador de Cache (para funciones)

```python
from proper.cache import cached

@cached(timeout=3600, key_prefix="posts")
def get_all_posts():
    # Esta función se cachea
    return Post.select()

# Invalidar cache
get_all_posts.cache_clear()
```

### Fragment Caching en Templates

```jinja
{% cache "sidebar", timeout=3600 %}
    <aside>
        {# Este contenido se cachea #}
    </aside>
{% endcache %}
```

---

## Queue (Colas de Trabajo)

Proper usa **Huey** para colas de trabajo en background.

### Configuración

```python
# En memoria (desarrollo)
QUEUE = {
    "type": "huey.MemoryHuey",
    "immediate": True,  # Ejecuta inmediatamente (sin cola)
}

# SQLite
QUEUE = {
    "type": "huey.SqliteHuey",
    "database": "db/queue.db",
    "immediate": False,
}

# Redis
QUEUE = {
    "type": "huey.RedisHuey",
    "host": "localhost",
    "port": 6379,
}

# Consumer config
QUEUE_CONSUMER = {
    "workers": 4,
    "periodic": True,  # Habilita tareas periódicas
}
```

### Definir Tareas

```python
# tasks/email.py
from ..main import app

queue = app.queue

@queue.task()
def send_welcome_email(user_id):
    from ..models import User
    from ..mailers import Mailer

    user = User.get_by_id(user_id)
    Mailer.welcome(user).send()

@queue.task(retries=3, retry_delay=60)
def process_image(image_path):
    # Procesar imagen
    pass

@queue.periodic_task(cron(minute="0", hour="*/6"))
def cleanup_old_sessions():
    # Se ejecuta cada 6 horas
    pass
```

### Encolar Tareas

```python
# En un controller
from ..tasks.email import send_welcome_email

def create_user(self):
    user = User.create(...)

    # Encolar tarea
    send_welcome_email(user.id)

    # O con delay:
    send_welcome_email.schedule(args=(user.id,), delay=60)  # En 60 segundos
```

### Consumer (Worker)

Ejecutar el worker:

```bash
# En desarrollo con Makefile:
make workers

# O directamente:
python workers.py
```

El archivo `workers.py`:

```python
from myapp.main import app

if __name__ == "__main__":
    consumer = app.queue.create_consumer(**app.config.QUEUE_CONSUMER)
    consumer.run()
```

---

## Email

### Configuración

```python
# Desarrollo (imprime en consola)
MAILER = {
    "type": "proper.mail.mailers.Console",
}

# SMTP
MAILER = {
    "type": "proper.mail.mailers.SMTP",
    "host": "smtp.gmail.com",
    "port": 587,
    "username": "user@example.com",
    "password": "secret",
    "use_tls": True,
}

# Amazon SES
MAILER = {
    "type": "proper.mail.mailers.AmazonSES",
    "region": "us-east-1",
    "access_key_id": "...",
    "secret_access_key": "...",
}

EMAIL_FROM = "noreply@example.com"
```

### Definir Mailers

```python
# mailers/mailer.py
from proper.mail import EmailMessage
from ..main import app

class Mailer:
    @staticmethod
    def welcome(user):
        return EmailMessage(
            to=user.email,
            from_email=app.config.EMAIL_FROM,
            subject="Welcome!",
            template="emails/welcome.jinja",
            context={"user": user},
        )

    @staticmethod
    def password_reset(user, token):
        return EmailMessage(
            to=user.email,
            from_email=app.config.EMAIL_FROM,
            subject="Reset your password",
            template="emails/password_reset.jinja",
            context={"user": user, "token": token},
        )
```

### Enviar Emails

```python
# Enviar inmediatamente
Mailer.welcome(user).send()

# Enviar en background (con queue)
from ..tasks.email import send_email

send_email.schedule(args=(Mailer.welcome(user),))
```

### Templates de Email

```jinja
{# views/emails/welcome.jinja #}
{% extends "layouts/email.jinja" %}

{% block content %}
<h1>Welcome, {{ user.name }}!</h1>

<p>Thank you for joining our platform.</p>

<a href="{{ url }}">Get Started</a>
{% endblock %}
```

---

## Internacionalización (i18n)

### Instalar Blueprint

```bash
proper install i18n
```

### Configuración

```python
# config/__init__.py
I18N = {
    "default_locale": "en",
    "supported_locales": ["en", "es", "fr"],
    "default_timezone": "UTC",
}
```

### Extraer Strings para Traducir

```bash
proper i18n extract
# Genera: locales/messages.pot
```

### Crear Traducción para un Idioma

```bash
proper i18n init es
# Genera: locales/es/LC_MESSAGES/messages.po
```

### Traducir

Editar `locales/es/LC_MESSAGES/messages.po`:

```
msgid "Hello, World!"
msgstr "¡Hola, Mundo!"

msgid "Welcome back, {name}!"
msgstr "¡Bienvenido de nuevo, {name}!"
```

### Compilar Traducciones

```bash
proper i18n compile
# Genera: locales/es/LC_MESSAGES/messages.mo
```

### Usar en Código

```python
# En controllers
message = self.app.i18n("Hello, World!")
message = self.app.i18n("Welcome back, {name}!", name=user.name)

# Plural
count = 5
message = self.app.i18n(
    "{count} item",
    "{count} items",
    count,
    count=count
)
```

### Usar en Templates

```jinja
{{ _("Hello, World!") }}
{{ _("Welcome back, {name}!", name=user.name) }}

{# Formatear fechas #}
{{ date|format_date }}
{{ date|format_datetime }}

{# Formatear números #}
{{ price|format_currency(currency='USD') }}
{{ number|format_decimal }}
```

### SetLocale Concern

```python
# controllers/concerns/set_locale.py (generado)
class SetLocale:
    def __call__(self, co):
        # Lee locale de cookie, query string, o Accept-Language
        locale = co.request.cookies.get("locale")
        if not locale:
            locale = co.request.query.get("locale")
        if not locale:
            supported = co.app.config.I18N["supported_locales"]
            locale = co.request.accept_language.best_match(supported)
        co.request.locale = locale or co.app.config.I18N["default_locale"]
```


---

## CLI (Command Line Interface)

Proper genera comandos CLI automáticamente.

### Comandos Incluidos

```bash
proper run      # Ejectura aplicacion usand gunicorn
proper routes   # Listas las rutas existentes

# Base de datos
proper db create migration_name    # Crear migración
proper db migrate                  # Aplicar migraciones
proper db rollback                 # Revertir última migración
proper db status                   # Ver estado de migraciones

# i18n (si está instalado)
proper i18n extract                # Extraer strings
proper i18n init locale            # Iniciar nueva traducción
proper i18n compile                # Compilar traducciones

# Generadores
proper generate model ModelName         # Generar modelo
proper generate controller ControllerName  # Generar controller
proper generate resource ResourceName   # Generar recurso completo
```

### Comandos Personalizados

```python
# myapp/cli/my_commands.py
from proper_cli import Arg, argument

def cleanup(app):
    """Limpia datos viejos"""
    # Usar el app
    db = app.db["main"]
    # ...

@argument("name", help="Name to greet")
def greet(app, name: Arg[str]):
    """Saluda a alguien"""
    print(f"Hello, {name}!")
```

Registrar:

```python
# myapp/cli/__init__.py
from . import my_commands

def register(CL):
    CL.add_command(my_commands.cleanup)
    CL.add_command(my_commands.greet)
```

Usar:

```bash
proper cleanup
proper greet John
```

---

## Mejores Prácticas

### 1. Estructura de Controllers

```python
# Jerarquía clara
BaseController          # Concerns comunes
├── PublicController   # Sin autenticación
└── PrivateController  # Requiere login
    ├── AdminController  # Requiere admin
    └── UserController   # Usuario regular
```

### 2. Concerns en Orden

```python
before = [
    RestoreSession(),           # 1. Restaurar sesión
    RestoreUser(),             # 2. Restaurar usuario
    RequireLogin(),            # 3. Verificar login
    RequireAdmin(),            # 4. Verificar permisos
    RequestForgeryProtection(), # 5. CSRF
]
```

### 3. Validación en Forms

Usa una librería de validación como `formidable`:

```python
from formidable import Form, Field, validators

class PostForm(Form):
    title = Field(validators=[
        validators.Required(),
        validators.Length(max=200),
    ])
    content = Field(validators=[
        validators.Required(),
    ])
```

### 4. Use Transactions

```python
with self.app.db["main"].atomic():
    user = User.create(...)
    profile = Profile.create(user=user, ...)
```

### 5. Flash Messages

```python
# En controller
self.response.flash.success("Post created!")
self.response.flash.info("Processing...")
self.response.flash.warning("Are you sure?")
self.response.flash.error("Something went wrong")

# En template
{% for type, message in request.flashes %}
    <div class="alert alert-{{ type }}">{{ message }}</div>
{% endfor %}
```

### 6. Error Handling

```python
from proper import errors

class MyController(BaseController):
    def show_post(self):
        post = Post.get_by_slug(self.params.get("slug"))
        if not post:
            raise errors.NotFound("Post not found")

        return self.render("posts/show.jinja", post=post)
```

---

## Recursos Adicionales

### Dependencias Principales

- **Peewee**: ORM - https://docs.peewee-orm.com/
- **Jinja2**: Templates - https://jinja.palletsprojects.com/
- **Huey**: Queue - https://huey.readthedocs.io/
- **Passlib**: Passwords - https://passlib.readthedocs.io/

### Estructura de un Request

```
Request
  ↓
head_to_get
  ↓
method_override
  ↓
match (Router)
  ↓
redirect (si aplica)
  ↓
dispatch (Controller)
  ↓
  before concerns
    ↓
  action method
    ↓
  after concerns
  ↓
strip_body_if_head
  ↓
Response
```

### Configuraciones Importantes

```python
# Seguridad
SECRET_KEYS = ["random-secret-key"]  # Rotar regularmente
MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB
MAX_QUERY_SIZE = 1024 * 1024  # 1MB

# Session
SESSION_COOKIE_LIFETIME = 60 * 60 * 24 * 7  # 7 días
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = True  # Solo en HTTPS
SESSION_COOKIE_SAMESITE = "Lax"

# Debug
DEBUG = False  # ¡NUNCA True en producción!
CATCH_ALL_ERRORS = True  # Captura errores en producción
```

---

## Conclusión

Proper es un framework que prioriza la **productividad del desarrollador** sin sacrificar poder o flexibilidad. Su diseño inspirado en Phoenix y Rails, combinado con las convenciones sensatas y el énfasis en código de aplicación sobre código de framework, lo hace ideal para construir aplicaciones web modernas en Python.

**Características clave**:
- Convention over Configuration
- No Globals
- App-code over Framework-code
- Class-based Controllers elegantes
- RESTful por defecto
- Autenticación, Cache, Queue integrados
- ORM con Migraciones
- Internacionalización

**Next Steps**:
1. Crea tu primera app: `uvx run proper-new myapp`
2. Explora los blueprints: `proper install auth`
3. Lee el código generado - es tu código para personalizar
4. Consulta esta guía cuando necesites referencia

¡Happy coding!
