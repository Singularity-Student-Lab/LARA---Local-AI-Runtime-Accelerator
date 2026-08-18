"""Mints the very first API key, out of band, directly against the database.

This solves the chicken-and-egg problem the blueprint names explicitly (section 21.9 point 4):
every admin endpoint requires an admin-capable API key, so the first one cannot be issued
through the API. This script creates the owner user if missing, then issues one active key
and prints the raw value exactly once. It is never re-runnable to reveal the same key - a
second run issues a NEW key rather than re-displaying the old one.

Run inside the gateway container:
    python -m database.seed.bootstrap_owner --username owner --display-name "Owner"
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select

from app.auth.keys import issue_key, hash_secret
from app.config import get_settings
from app.db.models import ApiKey, Role, User
from app.db.session import SessionLocal


async def main(username: str, display_name: str, label: str) -> None:
    settings = get_settings()
    async with SessionLocal() as db:
        owner_role = (await db.execute(select(Role).where(Role.name == "owner"))).scalar_one_or_none()
        if owner_role is None:
            raise SystemExit("owner role not found - run database.seed.seed first")

        user = (await db.execute(select(User).where(User.username == username))).scalar_one_or_none()
        if user is None:
            user = User(username=username, display_name=display_name, role_id=owner_role.id, enabled=True)
            db.add(user)
            await db.flush()
            print(f"Created owner user '{username}' ({user.id}).")
        else:
            print(f"Owner user '{username}' already exists ({user.id}). Issuing a new key for them.")

        key_id, secret, raw_key = issue_key()
        db.add(
            ApiKey(
                key_id=key_id,
                user_id=user.id,
                secret_hash=hash_secret(secret, settings.lara_api_key_pepper),
                label=label,
            )
        )
        await db.commit()

    print()
    print("=" * 72)
    print("OWNER API KEY - shown once, never stored or displayable again:")
    print()
    print(f"    {raw_key}")
    print()
    print("Store it now. Use it as: Authorization: Bearer " + raw_key)
    print("=" * 72)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", default="owner")
    parser.add_argument("--display-name", default="Owner")
    parser.add_argument("--label", default="bootstrap")
    args = parser.parse_args()
    asyncio.run(main(args.username, args.display_name, args.label))
