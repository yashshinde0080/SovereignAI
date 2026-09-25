"""Shared helpers.

Intentionally empty. Earlier revisions of this repository had ``file_utils.py``
and ``logger.py`` here (visible in the stale ``electron/dist`` bundle); those
files no longer exist and no module imports ``app.utils``, so this package
carries no code.

Kept as an explicit, documented package rather than a stray empty
``__init__.py`` so it does not read as a lost directory. Delete the directory
rather than parking scratch helpers here — logging config lives in
``app.main._configure_logging`` and path handling in ``app.config.Settings``.
"""
