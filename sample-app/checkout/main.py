"""Checkout microservice (KLR-B3) — processes orders."""

from shared.app_lib import create_app

_ORDERS = []


def place_order():
    order = {"id": len(_ORDERS) + 1, "items": ["cart-item"], "total": 42.0}
    _ORDERS.append(order)
    return order


def list_orders():
    return {"count": len(_ORDERS), "orders": _ORDERS[-10:]}


app = create_app("checkout", routes={"/orders": list_orders, "/orders/new": place_order})
