# Quran Reciter ID - Backend Application
# Auto-register /upload-fingerprints on any FastAPI app created in this package.
try:
    from fastapi import FastAPI as _F
    if not getattr(_F, "_upload_ep_patched", False):
        _orig = _F.__init__
        def _patched(self, *a, **k):
            _orig(self, *a, **k)
            try:
                from . import upload_endpoint as _ue
                _ue.register(self)
            except Exception as _e:
                import logging
                logging.getLogger(__name__).warning("upload_endpoint autoload failed: %s", _e)
        _F.__init__ = _patched
        _F._upload_ep_patched = True
except Exception:
    pass
