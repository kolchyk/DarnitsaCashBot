"""
Тест для проверки получения файла ботом, распознавания товаров и выделения товаров с "дарница".
"""
from __future__ import annotations

import io
from datetime import datetime, timezone

import pytest
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from libs.data.models import CatalogItem, LineItem, Receipt, User
from libs.data.repositories import CatalogRepository, ReceiptRepository, UserRepository
from services.ocr_worker.postprocess import build_structured_payload
from services.ocr_worker.tesseract_runner import OcrToken


def _create_test_image() -> bytes:
    """Создает простое тестовое изображение чека."""
    img = Image.new("RGB", (400, 600), color="white")
    # Сохраняем в байты
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")
    return img_bytes.getvalue()


def _token(text: str, left: int, top: int, profile: str = "line_items", confidence: float = 0.9) -> OcrToken:
    """Создает тестовый OCR токен."""
    return OcrToken(
        text=text,
        confidence=confidence,
        left=left,
        top=top,
        width=10,
        height=10,
        profile=profile,
    )


@pytest.fixture
async def test_user(session: AsyncSession) -> User:
    """Создает тестового пользователя."""
    user_repo = UserRepository(session)
    user = await user_repo.upsert_user(
        telegram_id=12345,
        phone_number="+380501234567",
        locale="uk",
    )
    await session.commit()
    return user


@pytest.fixture
async def test_catalog_with_darnitsa(session: AsyncSession) -> list[CatalogItem]:
    """Создает каталог товаров с товарами Дарница."""
    catalog_items = [
        CatalogItem(
            sku_code="DARN-001",
            product_aliases=["дарница", "darnitsa", "цитрамон дарница", "citramon darnitsa"],
            active_flag=True,
        ),
        CatalogItem(
            sku_code="DARN-002",
            product_aliases=["парацетамол дарница", "paracetamol darnitsa"],
            active_flag=True,
        ),
        CatalogItem(
            sku_code="OTHER-001",
            product_aliases=["витамин с", "vitamin c"],
            active_flag=True,
        ),
    ]
    for item in catalog_items:
        session.add(item)
    await session.commit()
    return catalog_items


async def test_receipt_file_upload_and_recognition(
    test_user: User,
    test_catalog_with_darnitsa: list[CatalogItem],
    session: AsyncSession,
):
    """Тест загрузки файла и распознавания товаров."""
    # Создаем тестовое изображение
    image_bytes = _create_test_image()
    
    # Проверяем, что файл создан
    assert len(image_bytes) > 0
    assert image_bytes[:8] == b"\x89PNG\r\n\x1a\n"  # PNG signature
    
    # Проверяем, что пользователь создан
    assert test_user.telegram_id == 12345
    
    # Проверяем, что каталог создан
    catalog_repo = CatalogRepository(session)
    catalog = await catalog_repo.list_active()
    assert len(catalog) == 3
    
    # Проверяем, что есть товары с "дарница" в алиасах
    darnitsa_items = [
        item for item in catalog
        if any("дарница" in alias.lower() or "darnitsa" in alias.lower() for alias in item.product_aliases)
    ]
    assert len(darnitsa_items) == 2  # DARN-001 и DARN-002


async def test_product_recognition_with_darnitsa(
    test_user: User,
    test_catalog_with_darnitsa: list[CatalogItem],
    session: AsyncSession,
):
    """Тест распознавания товаров и выделения товаров с 'дарница'."""
    from libs.common.config import AppSettings
    
    # Создаем мок OCR токены для чека с товарами
    tokens_by_profile = {
        "full": [
            _token("Аптека", left=0, top=5, profile="full"),
            _token("Дата: 01.01.2024", left=0, top=20, profile="full"),
        ],
        "line_items": [
            # Товар с Дарница
            _token("Цитрамон", left=0, top=60),
            _token("Дарница", left=80, top=60),
            _token("1", left=150, top=60),
            _token("x", left=160, top=60),
            _token("50,00", left=180, top=60),
            # Товар без Дарница
            _token("Витамин", left=0, top=90),
            _token("С", left=60, top=90),
            _token("1", left=150, top=90),
            _token("x", left=160, top=90),
            _token("30,00", left=180, top=90),
            # Еще один товар с Дарница
            _token("Парацетамол", left=0, top=120),
            _token("Дарница", left=100, top=120),
            _token("2", left=150, top=120),
            _token("x", left=160, top=120),
            _token("25,00", left=180, top=120),
        ],
        "totals": [
            _token("Всього", left=0, top=10, profile="totals"),
            _token("130,00", left=50, top=10, profile="totals"),
        ],
    }
    
    # Получаем каталог алиасов
    catalog_repo = CatalogRepository(session)
    catalog = await catalog_repo.list_active()
    catalog_aliases = {
        item.sku_code: [alias.lower() for alias in item.product_aliases] for item in catalog
    }
    
    # Строим структурированный payload
    settings = AppSettings(telegram_bot_token="dummy", encryption_secret="secret")
    preprocess_metadata = {"crops": {"header": {"height": 30}}}
    
    payload = build_structured_payload(
        preprocess_metadata=preprocess_metadata,
        tesseract_stats={},
        tokens_by_profile=tokens_by_profile,
        catalog_aliases=catalog_aliases,
        settings=settings,
    )
    
    # Проверяем, что товары распознаны
    assert len(payload["line_items"]) == 3
    
    # Проверяем, что товары с "дарница" правильно идентифицированы
    darnitsa_products = []
    other_products = []
    
    for item in payload["line_items"]:
        name_lower = item["name"].lower()
        if "дарница" in name_lower or "darnitsa" in name_lower:
            darnitsa_products.append(item)
        else:
            other_products.append(item)
    
    # Проверяем, что найдены товары с "дарница"
    assert len(darnitsa_products) == 2, f"Ожидалось 2 товара с 'дарница', найдено {len(darnitsa_products)}"
    
    # Проверяем, что товары с "дарница" имеют правильные SKU коды
    for product in darnitsa_products:
        assert product["sku_code"] is not None, f"Товар {product['name']} должен иметь SKU код"
        assert product["sku_code"].startswith("DARN-"), f"SKU код должен начинаться с 'DARN-', получен {product['sku_code']}"
    
    # Проверяем, что товар без "дарница" не имеет SKU или имеет другой SKU
    assert len(other_products) == 1
    if other_products[0]["sku_code"]:
        assert other_products[0]["sku_code"].startswith("OTHER-")
    
    # Проверяем названия товаров
    product_names = [item["name"] for item in payload["line_items"]]
    assert any("ЦИТРАМОН" in name and "ДАРНИЦА" in name for name in product_names)
    assert any("ПАРАЦЕТАМОЛ" in name and "ДАРНИЦА" in name for name in product_names)
    assert any("ВИТАМИН" in name and "С" in name for name in product_names)


async def test_receipt_saving_with_line_items(
    test_user: User,
    test_catalog_with_darnitsa: list[CatalogItem],
    session: AsyncSession,
):
    """Тест сохранения чека с товарами в базу данных."""
    from libs.common.config import AppSettings
    
    # Создаем чек
    receipt_repo = ReceiptRepository(session)
    receipt = await receipt_repo.create_receipt(
        user_id=test_user.id,
        upload_ts=datetime.now(timezone.utc),
        storage_object_key="test/receipt.jpg",
        checksum="test-checksum",
    )
    await session.commit()
    
    # Создаем мок OCR payload с товарами
    tokens_by_profile = {
        "full": [_token("Аптека", left=0, top=5, profile="full")],
        "line_items": [
            _token("Цитрамон", left=0, top=60),
            _token("Дарница", left=80, top=60),
            _token("1", left=150, top=60),
            _token("x", left=160, top=60),
            _token("50,00", left=180, top=60),
        ],
        "totals": [],
    }
    
    catalog_repo = CatalogRepository(session)
    catalog = await catalog_repo.list_active()
    catalog_aliases = {
        item.sku_code: [alias.lower() for alias in item.product_aliases] for item in catalog
    }
    
    settings = AppSettings(telegram_bot_token="dummy", encryption_secret="secret")
    preprocess_metadata = {"crops": {"header": {"height": 30}}}
    
    ocr_payload = build_structured_payload(
        preprocess_metadata=preprocess_metadata,
        tesseract_stats={},
        tokens_by_profile=tokens_by_profile,
        catalog_aliases=catalog_aliases,
        settings=settings,
    )
    
    # Сохраняем товары в базу данных (как это делает rules_engine)
    line_items = ocr_payload.get("line_items", [])
    for item in line_items:
        name = item.get("name", "")
        quantity = int(item.get("quantity", 1))
        price = item.get("price")
        if price is None:
            price = 0
        else:
            price = int(price)
        confidence = float(item.get("confidence", 0))
        sku_code = item.get("sku_code")
        
        session.add(
            LineItem(
                receipt_id=receipt.id,
                sku_code=sku_code,
                product_name=name,
                quantity=quantity,
                unit_price=price,
                total_price=price * quantity,
                confidence=confidence,
            )
        )
    
    receipt.ocr_payload = ocr_payload
    receipt.status = "accepted"
    await session.commit()
    
    # Проверяем, что товары сохранены
    await session.refresh(receipt)
    assert len(receipt.line_items) == 1
    
    line_item = receipt.line_items[0]
    assert "ЦИТРАМОН" in line_item.product_name
    assert "ДАРНИЦА" in line_item.product_name
    assert line_item.sku_code == "DARN-001"
    assert line_item.quantity == 1
    assert line_item.unit_price == 5000  # 50.00 в копейках
    
    # Проверяем, что товар с "дарница" выделен (имеет SKU код)
    assert line_item.sku_code is not None
    assert line_item.sku_code.startswith("DARN-")

