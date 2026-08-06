"""Inventory microservice (KLR-B3) — stock levels."""

from shared.app_lib import create_app

_INVENTORY = {"SKU-1": 100, "SKU-2": 250, "SKU-3": 0}


def stock():
    return {"inventory": _INVENTORY}


app = create_app("inventory", routes={"/inventory": stock})
