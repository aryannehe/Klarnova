"""Cart microservice (KLR-B3) — shopping carts."""

from shared.app_lib import create_app

_CARTS = []


def carts():
    return {"count": len(_CARTS), "carts": _CARTS[-10:]}


app = create_app("cart", routes={"/carts": carts})
