from proper import show_banner, show_welcome


host = "0.0.0.0"
port = 2300


wsgi_app = "app.main:app"

# The socket to bind.
# A string of the form: 'HOST', 'HOST:PORT', 'unix:PATH'.
# An IP is a valid HOST.
bind = f"{host}:{port}"

reload = True
reload_extra_files = []


# The number of worker processes that this server
# should keep alive for handling requests.
#
# A positive integer generally in the 2-4 x $(NUM_CORES)
# range. You'll want to vary this a bit to find the best
# for your particular application's work load.
workers = 1

# The type of workers to use. The default
# sync class should handle most 'normal' types of work
# loads. You'll want to read
# http://docs.gunicorn.org/en/latest/design.html#choosing-a-worker-type
# for information on when you might want to choose one
# of the other worker classes.
worker_class = "sync"

# For the eventlet and gevent worker classes
# this limits the maximum number of simultaneous clients that
# a single process can handle.
#
# A positive integer generally set to around 1000.
worker_connections = 1000

# If a worker does not notify the master process in this
# number of seconds it is killed and a new worker is spawned
# to replace it.
#
# Generally set to thirty seconds. Only set this noticeably
# higher if you're sure of the repercussions for sync workers.
# For the non sync workers it just means that the worker
# process is still communicating and is not tied to the length
# of time required to handle a single request.
timeout = 30

# The number of seconds to wait for the next request
# on a Keep-Alive HTTP connection.
#
# A positive integer. Generally set in the 1-5 seconds range.
keepalive = 2


# The path to a log file to write to.
# A path string. "-" means log to stdout.
accesslog = "-"
errorlog = "-"

# The granularity of log output
# A string of "debug", "info", "warning", "error", "critical"
loglevel = "info"

access_log_format = "%(r)s | %(B)s bytes in %(M)s ms"


#A base to use with setproctitle to change the way
# that Gunicorn processes are reported in the system process
# table. This affects things like 'ps' and 'top'.
proc_name = "[[ app_name ]]"


def on_starting(server):
    show_banner()


def when_ready(server):
    show_welcome(host, port)


def pre_exec(server):
    show_welcome(host, port)
