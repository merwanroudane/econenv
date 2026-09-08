"""IPython magics.

Registration policy, which is the whole of brief §3 and §7 in one place:

* **Stata** — PyStata's own ``%stata`` / ``%%stata`` / ``%mata`` are loaded, not
  copied. EconEnv never defines a magic by those names.
* **R** — when rpy2 is importable, rpy2's official ``%R`` / ``%%R`` are loaded.
  EconEnv's own R magic is always available as ``%Rec`` / ``%%Rec`` and claims
  the short ``%R`` / ``%%R`` names **only when nothing else has**.
* **EViews** — no official IPython magic exists, so ``%eviews`` / ``%%eviews``
  are ours.
* **Management** — ``%econ`` is ours and is namespaced to avoid any collision.

``%econ engines`` prints which implementation actually won each name, so the
answer is never a guess.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .._logging import get_logger

_log = get_logger("magics")

#: Filled in by :func:`register_all`; reported by ``%econ engines``.
REGISTRATION: Dict[str, str] = {}


def register_all(ipython: Any) -> Dict[str, str]:
    """Register every EconEnv magic into *ipython*, resolving collisions."""
    from .econ_magic import EconMagics
    from .econlang_magic import EconLangMagics
    from .eviews_magic import EViewsMagics
    from .gauss_magic import GaussMagics
    from .matlab_magic import MatlabMagics
    from .r_magic import RMagics, claim_short_r_names, load_rpy2_magics
    from .stata_magic import load_stata_magics

    REGISTRATION.clear()

    ipython.register_magics(EconMagics)
    REGISTRATION["%econ"] = "econenv"

    ipython.register_magics(RMagics)
    REGISTRATION["%Rec / %%Rec"] = "econenv"

    if load_rpy2_magics(ipython):
        REGISTRATION["%R / %%R"] = "rpy2 (official)"
    elif claim_short_r_names(ipython):
        REGISTRATION["%R / %%R"] = "econenv (rpy2 not installed)"
    else:
        REGISTRATION["%R / %%R"] = "already taken by another extension — use %Rec"

    ipython.register_magics(EViewsMagics)
    REGISTRATION["%eviews / %%eviews"] = "econenv"

    ipython.register_magics(MatlabMagics)
    REGISTRATION["%matlab / %%matlab"] = "econenv"

    ipython.register_magics(GaussMagics)
    REGISTRATION["%gauss / %%gauss"] = "econenv"

    ipython.register_magics(EconLangMagics)
    REGISTRATION["%%econlang"] = "econenv"

    status = load_stata_magics(ipython)
    REGISTRATION["%stata / %%stata"] = status

    return dict(REGISTRATION)


def registration_lines() -> List[str]:
    return [f"{name:<22} {owner}" for name, owner in REGISTRATION.items()]
