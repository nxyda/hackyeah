"""Generate reproducible test reports around a Krakow walking corridor."""

import argparse
import asyncio
import random
from datetime import datetime, timedelta, timezone

from geoalchemy2 import WKTElement
from sqlalchemy import select

from app.database.session import SessionFactory
from app.enums.report import ReportCategory
from app.models.report import Report
from app.models.user import User


DEFAULT_BOUNDS = (19.9340, 19.9470, 50.0600, 50.0705)


def build_reports(count: int, seed: int) -> list[dict[str, object]]:
    """Build deterministic report payloads without touching the database."""

    if count <= 0:
        raise ValueError("count must be positive")
    rng = random.Random(seed)
    categories = tuple(ReportCategory)
    now = datetime.now(timezone.utc)
    reports = []
    for _ in range(count):
        longitude = rng.uniform(DEFAULT_BOUNDS[0], DEFAULT_BOUNDS[1])
        latitude = rng.uniform(DEFAULT_BOUNDS[2], DEFAULT_BOUNDS[3])
        reports.append(
            {
                "category": rng.choice(categories),
                "longitude": longitude,
                "latitude": latitude,
                "confirmations": rng.randint(0, 5),
                "created_at": now - timedelta(minutes=rng.randint(0, 180)),
                "expires_at": now + timedelta(hours=rng.randint(2, 12)),
            }
        )
    return reports


async def apply_reports(payloads: list[dict[str, object]]) -> int:
    """Insert generated reports for the first active user."""

    async with SessionFactory() as session:
        user = (
            await session.execute(
                select(User).where(User.is_active.is_(True)).order_by(User.id).limit(1)
            )
        ).scalar_one_or_none()
        if user is None:
            raise RuntimeError("cannot generate reports: no active user exists")
        for payload in payloads:
            session.add(
                Report(
                    user_id=user.id,
                    category=payload["category"],
                    geom=WKTElement(
                        f"POINT({payload['longitude']} {payload['latitude']})",
                        srid=4326,
                    ),
                    created_at=payload["created_at"],
                    expires_at=payload["expires_at"],
                    confirmations=payload["confirmations"],
                )
            )
        await session.commit()
        return user.id


def parse_args() -> argparse.Namespace:
    """Parse generator options."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20261004)
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args()


async def main() -> None:
    """Print generated reports and optionally persist them."""

    args = parse_args()
    payloads = build_reports(args.count, args.seed)
    if args.apply:
        user_id = await apply_reports(payloads)
        print(f"inserted {len(payloads)} reports for user_id={user_id}")
    else:
        for payload in payloads:
            print(
                payload["category"].value,
                f"{payload['latitude']:.6f},{payload['longitude']:.6f}",
                f"confirmations={payload['confirmations']}",
            )
        print("dry run only; rerun with --apply to insert these reports")


if __name__ == "__main__":
    asyncio.run(main())
