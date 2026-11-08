"""
CargoLens AI — Dedicated Demo Users Seed CLI
Idempotently ensures demo accounts exist in the database without modifying shipments, documents, or unrelated users.
"""
import argparse
import asyncio
import logging
import sys

from app.config import settings
from app.database import AsyncSessionFactory, dispose_engine
from app.cli.seed_demo import seed_users

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("cargolens.seed_users")


async def run_seed_users(force: bool = False, overwrite_passwords: bool = False):
    """Idempotently seeds demo users."""
    if not force and settings.ENVIRONMENT.lower() in ("production", "prod") and not settings.ALLOW_DEMO_SEEDING:
        logger.error("Refusing to run seed_users in PRODUCTION environment without --force flag!")
        sys.exit(1)

    logger.info("Idempotently verifying/seeding demo user accounts...")
    try:
        async with AsyncSessionFactory() as session:
            await seed_users(session, overwrite_passwords=overwrite_passwords)
        logger.info("=================================================================")
        logger.info("CargoLens AI demo user accounts successfully verified/seeded!")
        logger.info("  1. executive@cargolens.in / DemoExecutive2026! (Documentation Executive)")
        logger.info("  2. manager@cargolens.in   / DemoManager2026!   (Documentation Manager)")
        logger.info("=================================================================")
    finally:
        await dispose_engine()


def main():
    parser = argparse.ArgumentParser(description="CargoLens AI Demo Users Seeding Tool")
    parser.add_argument("--force", action="store_true", help="Force execution in production")
    parser.add_argument("--overwrite-passwords", action="store_true", help="Overwrite existing demo account passwords")
    args = parser.parse_args()

    asyncio.run(run_seed_users(force=args.force, overwrite_passwords=args.overwrite_passwords))


if __name__ == "__main__":
    main()
