"""Admin user and API-key management (blueprint section 3, Session 3 point 3-4).

Manual provisioning only - no open registration (PRD 4.2). Every mutating action writes an
audit_events row with actor, target, and timestamp, never the secret itself (PRD 16.4)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.api.errors import lara_error
from app.auth.dependencies import AuthContext, require_admin
from app.auth.keys import hash_secret, issue_key
from app.config import Settings, get_settings
from app.db.models import ApiKey, AuditEvent, Role, User
from app.db.session import get_db

router = APIRouter()


class CreateUserRequest(BaseModel):
    username: str
    display_name: str
    role: str
    enabled: bool = True


class PatchUserRequest(BaseModel):
    display_name: str | None = None
    role: str | None = None
    enabled: bool | None = None


class IssueKeyRequest(BaseModel):
    label: str | None = None


def _user_out(user: User, role_name: str) -> dict:
    return {
        "id": str(user.id),
        "username": user.username,
        "display_name": user.display_name,
        "role": role_name,
        "enabled": user.enabled,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


async def _audit(db: AsyncSession, ctx: AuthContext, event_type: str, target: str, detail: dict) -> None:
    db.add(
        AuditEvent(
            actor_user_id=ctx.user.id,
            event_type=event_type,
            target=target,
            detail=detail,
        )
    )


@router.post("/admin/users", status_code=201)
async def create_user(
    request: Request,
    body: CreateUserRequest,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_admin),
) -> dict:
    role = (await db.execute(select(Role).where(Role.name == body.role))).scalar_one_or_none()
    if role is None:
        raise lara_error(400, "unknown_role", f"Unknown role '{body.role}'.", request)

    existing = (await db.execute(select(User).where(User.username == body.username))).scalar_one_or_none()
    if existing is not None:
        raise lara_error(409, "duplicate_username", f"Username '{body.username}' already exists.", request)

    user = User(username=body.username, display_name=body.display_name, role_id=role.id, enabled=body.enabled)
    db.add(user)
    await db.flush()
    await _audit(db, ctx, "user.create", str(user.id), {"username": body.username, "role": body.role})
    await db.commit()
    return _user_out(user, role.name)


@router.get("/admin/users")
async def list_users(
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_admin),
) -> list[dict]:
    result = await db.execute(select(User, Role).join(Role, User.role_id == Role.id))
    return [_user_out(u, r.name) for u, r in result.all()]


@router.get("/admin/users/{user_id}")
async def get_user(
    request: Request,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_admin),
) -> dict:
    row = (
        await db.execute(select(User, Role).join(Role, User.role_id == Role.id).where(User.id == user_id))
    ).first()
    if row is None:
        raise lara_error(404, "user_not_found", "Unknown user.", request)
    user, role = row
    return _user_out(user, role.name)


@router.patch("/admin/users/{user_id}")
async def patch_user(
    request: Request,
    user_id: uuid.UUID,
    body: PatchUserRequest,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_admin),
) -> dict:
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise lara_error(404, "user_not_found", "Unknown user.", request)

    changes: dict = {}
    if body.display_name is not None:
        user.display_name = body.display_name
        changes["display_name"] = body.display_name
    if body.role is not None:
        role = (await db.execute(select(Role).where(Role.name == body.role))).scalar_one_or_none()
        if role is None:
            raise lara_error(400, "unknown_role", f"Unknown role '{body.role}'.", request)
        user.role_id = role.id
        changes["role"] = body.role
    if body.enabled is not None:
        user.enabled = body.enabled
        changes["enabled"] = body.enabled

    if changes:
        event_type = "user.disable" if changes.get("enabled") is False else "user.update"
        await _audit(db, ctx, event_type, str(user.id), changes)
    await db.commit()

    role = (await db.execute(select(Role).where(Role.id == user.role_id))).scalar_one()
    return _user_out(user, role.name)


@router.post("/admin/users/{user_id}/api-keys", status_code=201)
async def issue_api_key(
    request: Request,
    user_id: uuid.UUID,
    body: IssueKeyRequest,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_admin),
    settings: Settings = Depends(get_settings),
) -> dict:
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise lara_error(404, "user_not_found", "Unknown user.", request)

    key_id, secret, raw_key = issue_key()
    db.add(
        ApiKey(
            key_id=key_id,
            user_id=user.id,
            secret_hash=hash_secret(secret, settings.lara_api_key_pepper),
            label=body.label,
        )
    )
    await _audit(db, ctx, "key.issue", key_id, {"user_id": str(user.id), "label": body.label})
    await db.commit()

    # The only place the raw key is ever returned. Never logged, never stored, never shown again.
    return {"key_id": key_id, "api_key": raw_key, "label": body.label}


@router.get("/admin/users/{user_id}/api-keys")
async def list_api_keys(
    request: Request,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_admin),
) -> list[dict]:
    result = await db.execute(select(ApiKey).where(ApiKey.user_id == user_id))
    return [
        {
            "key_id": k.key_id,
            "label": k.label,
            "created_at": k.created_at.isoformat() if k.created_at else None,
            "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
            "revoked_at": k.revoked_at.isoformat() if k.revoked_at else None,
        }
        for k in result.scalars().all()
    ]


@router.delete("/admin/api-keys/{key_id}", status_code=204)
async def revoke_api_key(
    request: Request,
    key_id: str,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_admin),
) -> Response:
    key = (await db.execute(select(ApiKey).where(ApiKey.key_id == key_id))).scalar_one_or_none()
    if key is None:
        raise lara_error(404, "key_not_found", "Unknown API key.", request)
    key.revoked_at = datetime.now(timezone.utc)
    await _audit(db, ctx, "key.revoke", key_id, {})
    await db.commit()
    return Response(status_code=204)
