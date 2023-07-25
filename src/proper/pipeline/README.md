## proper.pipeline

This folder contains the pipeline of funcions used to process a request, dispatch it to a controller, and prost-process the response.

Each of these functions take a request, a response, and an application instance.
They return nothing, all side-effects must be on the request and/or the response instances.
