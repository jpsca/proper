import random
from pathlib import Path

from jinja2 import Markup
from proper import App

from [[ name ]].config import config


app = App("[[ name ]]", config=config)


def include_static(path):
    """Read and returns a text file from the `static` folder, to include
    in the template as-is.
    """
    text = (app.static_path / path).read_text()
    return Markup(text)

app.render.globals["include_static"] = include_static



def shuffle(iter, seed=None):
    random.seed(seed)
    iter = iter[:]
    random.shuffle(iter)
    return iter

app.render.filters["shuffle"] = shuffle
