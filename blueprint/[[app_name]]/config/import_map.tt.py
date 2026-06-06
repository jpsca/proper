# Lets browsers resolve JS package names (like "@hotwired/stimulus") to local or CDN files.
# It allows you to import JS files without needing to process them first with a bundler.
# The values must be paths relative to `[[app_name]]/assets/` or an URL.
IMPORT_MAP = {
    "@hotwired/stimulus": "js/vendor/stimulus.js",
    "@hotwired/turbo": "js/vendor/turbo.js",
}
