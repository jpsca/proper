import markdown


markdowner = markdown.Markdown(extensions=[
    "admonition",
    "attr_list",
    "codehilite",
    "smarty",
    "tables",
    "pymdownx.betterem",
    "pymdownx.caret",
    "pymdownx.details",
    "pymdownx.emoji",
    "pymdownx.keys",
    "pymdownx.magiclink",
    "pymdownx.mark",
    "pymdownx.smartsymbols",
    "pymdownx.superfences",
    "pymdownx.tabbed",
    "pymdownx.tasklist",
    "pymdownx.tilde",
])


def convert_markdown(md):
    return markdowner.convert(md)
