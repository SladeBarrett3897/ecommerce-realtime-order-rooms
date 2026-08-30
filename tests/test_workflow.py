import pytest

from src.realtime_service import event_for_status


def test_order_status_maps_to_customer_room_event():
    assert event_for_status("fulfilled") == "order.fulfillment"
    assert event_for_status("receipt") == "order.receipt"


def test_unknown_status_is_rejected_before_publish():
    with pytest.raises(ValueError):
        event_for_status("refunded")
