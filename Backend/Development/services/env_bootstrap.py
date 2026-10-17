"""
Environment bootstrap (design §0)
=================================

Loads ``Backend/.env`` into ``os.environ`` **once, at import time**, so that any
module which imports this one *before* constructing a boto3 client sees the AWS
credentials + region from the committed ``.env`` file.

Why an import-time side effect (not a function call in ``main.py``'s body):
Python runs a module's ``import`` statements before any of its function bodies,
and several modules construct boto3 clients/resources at module scope. By making
``import services.env_bootstrap`` the *first* import (physically above the boto3
construction lines) in ``main.py`` and ``services/dynamodb_client.py``, the
``load_dotenv`` below runs before those clients are built.

Secrets are referenced by env-var NAME only; no secret value is ever logged.
``AWS_ACCESS_KEY_ID`` / ``AWS_SECRET_ACCESS_KEY`` / ``AWS_REGION`` live in the
``.env`` file and are never printed by this module.
"""

from pathlib import Path

from dotenv import load_dotenv

# Backend/.env lives two levels up from Backend/Development/services/
#   services/ -> Development/ -> Backend/   (parents[2])
_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


def load_backend_env() -> None:
    """Load ``Backend/.env`` into ``os.environ`` if the file exists.

    Idempotent and safe to call repeatedly. ``override=False`` means a value
    already present in the real environment (e.g. a configured deployment) wins
    over the committed ``.env``. Does nothing (and never raises) when the file
    is absent.
    """
    if _ENV_PATH.exists():
        load_dotenv(dotenv_path=_ENV_PATH, override=False)


# Import side effect: load immediately so that any module importing env_bootstrap
# BEFORE constructing a boto3 client gets Backend/.env in os.environ in time.
load_backend_env()
