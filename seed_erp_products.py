"""Seed erp_products table from ERP_LIST.csv.

Run AFTER migrations have been applied.

Usage:
    DATABASE_URL=postgresql+asyncpg://... uv run python seed_erp_products.py /path/to/ERP_LIST.csv
    DATABASE_URL=postgresql+asyncpg://... uv run python seed_erp_products.py  # looks for ERP_LIST.csv in cwd
"""

import asyncio
import csv
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from coa_db_models.erp.models import ErpProduct

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def to_slug(text: str) -> str:
    slug = text.lower()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    return slug.strip("_")


def parse_connection_methods(row: dict) -> list[str]:
    methods: list[str] = []
    if row.get("CSV", "").strip():
        methods.append("csv_file")
    if row.get("MCP", "").strip():
        methods.append("mcp_server")
    return methods


async def seed_erp_products(session: AsyncSession, csv_path: Path) -> None:
    existing = await session.execute(select(ErpProduct))
    if existing.scalars().first():
        logger.info("erp_products already seeded — skipping")
        return

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        products: list[ErpProduct] = []
        seen_ids: set[str] = set()
        for row in reader:
            product_name = row["Product"].strip()
            vendor = row["Vendor"].strip()
            product_id = to_slug(product_name)

            # Deduplicate slugs by appending a counter
            base_id = product_id
            counter = 2
            while product_id in seen_ids:
                product_id = f"{base_id}_{counter}"
                counter += 1
            seen_ids.add(product_id)

            products.append(
                ErpProduct(
                    id=product_id,
                    vendor=vendor,
                    product_name=product_name,
                    connection_methods=parse_connection_methods(row),
                )
            )

    session.add_all(products)
    await session.commit()
    logger.info("Seeded %d ERP products", len(products))


async def main() -> None:
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("ERP_LIST.csv")
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is not set")

    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        await seed_erp_products(session, csv_path)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
