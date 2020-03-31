#!/usr/bin/env python
"""
This file generates all the necessary files for packaging for the project.
Read more about it at https://github.com/jpscaletti/mastermold/
"""
data = {
    "title": "Proper",
    "name": "proper",
    "pypi_name": "proper",
    "version": "1.191212",
    "author": "Juan-Pablo Scaletti",
    "author_email": "juanpablo@jpscaletti.com",
    "description": "A web framework optimized for programmer happiness.",
    "copyright": "2019",
    "repo_name": "jpscaletti/proper",
    "home_url": "https://properframework.dev",
    # Displayed in the pypi project page
    "project_urls": {
        # "Documentation": "https://properframework.dev/docs",
    },
    "extra_classifiers": [
    ],
    "development_status": "4 - Beta",
    "minimal_python": 3.6,
    "install_requires": [
        "gevent ~= 1.4",
        "gevent-websocket",
        "hecto ~= 1.200121",
        "itsdangerous ~= 1.1",
        "jinja2 ~= 2.10",
        "multipart ~= 0.2",
        "passlib ~= 1.7",
        "pyceo ~= 2.20204",
        "proper_config ~= 1.200331",
        "ujson ~= 2.0",
        "wsaccel ~= 0.6",
    ],
    "testing_requires": [
        "pytest",
        "pytest-cov",
        "WebTest",
    ],
    "development_requires": [
        "pytest-flake8",
        "flake8",
        "ipdb",
        "tox",
        "mkdocs",
        "pymdown-extensions",
        "pygments",
        "pygments-github-lexers",
    ],
    "entry_points": "proper = proper.cli:start",
    "coverage_omit": [
        "proper/base_channel.py",
        "proper/cli.py",
        "proper/server.py",
        "proper/router/channel.py",
    ],
}


def do_the_thing():
    import hecto

    hecto.copy(
        # "gh:jpscaletti/mastermold.git",
        "../mastermold",  # Path to the local copy of Master Mold
        ".",
        data=data,
        force=False,
    )


if __name__ == "__main__":
    do_the_thing()
