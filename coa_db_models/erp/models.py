import uuid

from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from coa_db_models.base import Base


class ErpCompatibilityRule(Base):
    __tablename__ = "erp_compatibility_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_product_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    target_product_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    connection_method_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_compatible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    incompatibility_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class ErpProduct(Base):
    """ERP product catalogue populated from ERP_LIST.csv.

    Three core data columns: vendor, product_name, connection_methods.
    """

    __tablename__ = "erp_products"

    id: Mapped[str] = mapped_column(String(150), primary_key=True)
    vendor: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    product_name: Mapped[str] = mapped_column(String(300), nullable=False)
    connection_methods: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
