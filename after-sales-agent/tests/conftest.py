import pytest
from src.core.config import Settings


@pytest.fixture
def test_settings():
    return Settings(
        anthropic_api_key="test-key",
        model_id="claude-sonnet-4-6",
        database_path=":memory:",
        log_level="DEBUG",
    )


@pytest.fixture
def sample_ticket():
    return {
        "ticket_id": "TK20260601-0001",
        "buyer_id": "user_123",
        "order_id": "order_456",
        "product_name": "XX品牌氨基酸洁面150ml",
        "product_sku": "LP-001",
        "reason": "用了两次脸上泛红起小疙瘩",
        "images": [],
        "demand": "退货退款",
        "order_amount": 189.0,
        "purchase_date": "2026-05-15",
        "platform": "淘宝",
        "historical_return_count": 0,
    }


@pytest.fixture
def sample_allergy_ticket(sample_ticket):
    return {
        **sample_ticket,
        "ticket_id": "TK20260601-0002",
        "reason": "用完脸颊红肿，起了很多小疹子，以前没有过敏史",
        "images": ["skin_photo_1.jpg"],
    }
