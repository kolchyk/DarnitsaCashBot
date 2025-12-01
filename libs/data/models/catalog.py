from __future__ import annotations

from sqlalchemy import Boolean, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from libs.data.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class CatalogItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "catalog_items"

    sku_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    product_aliases: Mapped[list[str]] = mapped_column(JSON, default_factory=list)
    active_flag: Mapped[bool] = mapped_column(Boolean, default=True)

