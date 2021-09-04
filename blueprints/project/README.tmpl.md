# [[ app_name ]]

A *Proper* web application.


## Installation

## Without Docker:
1. Create a virtualenv
2. `make setup`
3. Run with `make run`

## With docker:
`docker-compose up --build`

After the container is running, to execute any command inside the container, like running tests, etc. you need to use `docker-compose exec SERVICE COMMAND`.
For example: `docker-compose exec app make lint`


## Manage requirements

This project uses [pip-tools](https://github.com/jazzband/pip-tools/) to manage its requirements and pin them to specific versions. Using the specific versions of the libraries that we know work, makes our builds are predictable and deterministic.

Note: If you are running the app with Docker, don't forget to prepend these commands with `docker-compose exec app` to run them inside the container e.g.: `docker-compose exec app pip-compile`

### To add a new requirement

1. Edit the `requirements/requirements.ini` file and add a new requirement to the list (e.g. `rq`).
  You can optionally add constraints to which versions are acceptable, e.g.: `rq <3.0`
2. Run `make reqs`

### To upgrade a requirement

To upgrade a requirement to its latest version run:

`pip-compile --upgrade-package NAME requirements/requirements.ini`
