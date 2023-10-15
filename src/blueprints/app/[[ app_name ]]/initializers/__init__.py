"""Import all the modules in this folder."""
from importlib import import_module
from pathlib import Path
from pkgutil import iter_modules


# iterate through the modules in the current package
package_dir = str(Path(__file__).resolve().parent)
for (_, module_name, __) in iter_modules([package_dir]):
    import_module(f"{__name__}.{module_name}")
