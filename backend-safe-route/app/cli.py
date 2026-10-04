"""Polecenia administracyjne uruchamiane z terminala."""

import argparse
import asyncio
import getpass

from app.database.session import SessionFactory
from app.enums.user_role import UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.auth import RegisterRequest
from app.services.auth_service import password_hasher


async def create_admin(email: str, password: str) -> None:
    details = RegisterRequest(email=email, password=password)
    async with SessionFactory() as session:
        repository = UserRepository(session)
        user = await repository.get_by_email(str(details.email))
        password_hash = await asyncio.to_thread(password_hasher.hash, details.password)
        if user is None:
            user = await repository.create(
                email=str(details.email).strip().lower(),
                password_hash=password_hash,
            )
        else:
            user.password_hash = password_hash
            user.is_active = True
            user.role = UserRole.ADMIN
        user.role = UserRole.ADMIN
        await session.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Safe Route administration")
    subparsers = parser.add_subparsers(dest="command", required=True)
    create_admin_parser = subparsers.add_parser(
        "create-admin",
        help="Create an administrator or promote an existing account",
    )
    create_admin_parser.add_argument("--email", required=True)
    args = parser.parse_args()

    password = getpass.getpass("Admin password (minimum 12 characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        parser.error("Passwords do not match")
    if len(password) < 12 or len(password) > 1024:
        parser.error("Password must contain between 12 and 1024 characters")
    asyncio.run(create_admin(args.email, password))
    print(f"Administrator account ready: {args.email.strip().lower()}")


if __name__ == "__main__":
    main()
