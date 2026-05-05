from __future__ import annotations

from app.integrations.bitrix24 import Bitrix24Integration, Bitrix24Service


def test_bitrix24_integration_has_only_read_methods() -> None:
    forbidden = [
        "create_lead",
        "update_lead",
        "delete_lead",
        "create_deal",
        "update_deal",
        "delete_deal",
        "create_contact",
        "update_contact",
        "delete_contact",
    ]
    for method_name in forbidden:
        assert not hasattr(Bitrix24Integration, method_name)
        assert not hasattr(Bitrix24Service, method_name)
