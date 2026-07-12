# Compatibility shim: some Hermes plugin loaders look for init.py as the
# entrypoint. Mirror the real plugin in __init__.py.
from __init__ import register  # noqa: F401
