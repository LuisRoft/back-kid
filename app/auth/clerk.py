"""Clerk JWT verification + FastAPI dependency.

The frontend signs requests to private endpoints (currently `/agent/chat`)
with a Clerk session token. This module:

  1. Fetches Clerk's JWKS (rotated public keys) and caches it in memory.
  2. Verifies the JWT signature (RS256) and standard claims (iss, exp, nbf).
  3. Pulls the user profile out of the token's `unsafe_metadata` claim (or
     a flattened `profile` claim if the JWT template provides it).
  4. Exposes `get_current_user` as a FastAPI dependency.

Configure Clerk's JWT Template to include the user's metadata:

    {
        "profile": "{{user.unsafe_metadata}}"
    }
"""
from __future__ import annotations

import logging
import time
from typing import Any

import httpx
import jwt
from fastapi import Depends, HTTPException, Request, status
from pydantic import BaseModel

from app.config import settings

log = logging.getLogger(__name__)

JWKS_CACHE_TTL_SECONDS = 60 * 60  # 1h


# -------------------------------------------------------------------- Models


class CitizenLocation(BaseModel):
    lat: float
    lon: float
    label: str | None = None


class CitizenProfile(BaseModel):
    """Mirror of the FE-side shape stored in Clerk `unsafeMetadata.profile`."""

    onboarding_complete: bool = False
    location: CitizenLocation | None = None
    family_size: int | None = None
    has_kids: bool = False
    has_elderly: bool = False
    medical_conditions: list[str] = []
    has_vehicle: bool = False
    alternate_shelter: CitizenLocation | None = None
    locale: str | None = None

    model_config = {"populate_by_name": True, "extra": "ignore"}


class CurrentUser(BaseModel):
    clerk_user_id: str
    email: str | None = None
    profile: CitizenProfile | None = None


# ------------------------------------------------------------------- JWKS cache


class _JWKSCache:
    def __init__(self) -> None:
        self._jwks: dict[str, Any] | None = None
        self._fetched_at: float = 0.0
        self._url: str = ""

    async def get(self, url: str) -> dict[str, Any]:
        now = time.monotonic()
        if (
            self._jwks is not None
            and self._url == url
            and now - self._fetched_at < JWKS_CACHE_TTL_SECONDS
        ):
            return self._jwks

        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(url)
            r.raise_for_status()

        self._jwks = r.json()
        self._fetched_at = now
        self._url = url
        return self._jwks


_jwks_cache = _JWKSCache()


# ---------------------------------------------------------------- Verification


def _jwks_url() -> str:
    if settings.CLERK_JWKS_URL:
        return settings.CLERK_JWKS_URL
    if settings.CLERK_JWT_ISSUER:
        return f"{settings.CLERK_JWT_ISSUER.rstrip('/')}/.well-known/jwks.json"
    raise HTTPException(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "Clerk JWT verification is not configured (set CLERK_JWT_ISSUER or CLERK_JWKS_URL)",
    )


def _jwt_issuer() -> str | None:
    if not settings.CLERK_JWT_ISSUER:
        return None
    return settings.CLERK_JWT_ISSUER.rstrip("/")


def _get_signing_key(jwks: dict[str, Any], kid: str | None):
    if not kid:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "JWT missing `kid` header")
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return jwt.PyJWK(key).key
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown signing key")


async def verify_token(token: str) -> dict[str, Any]:
    """Verify a Clerk session token and return its decoded claims."""
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Malformed JWT") from exc

    jwks = await _jwks_cache.get(_jwks_url())
    signing_key = _get_signing_key(jwks, header.get("kid"))

    try:
        claims = jwt.decode(
            token,
            key=signing_key,
            algorithms=["RS256"],
            issuer=_jwt_issuer(),
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "JWT expired") from exc
    except jwt.InvalidIssuerError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid JWT issuer") from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid JWT: {exc}") from exc

    return claims


# --------------------------------------------------------------- Profile parse


def _extract_profile(claims: dict[str, Any]) -> CitizenProfile | None:
    """Pull the citizen profile out of a few possible claim layouts:

    1. `profile` claim, already shaped as CitizenProfile (preferred).
    2. `unsafe_metadata.profile` (when the JWT template returns full metadata).
    3. `unsafe_metadata` directly looks like a profile (legacy).
    """
    candidate: Any = None
    profile_claim = claims.get("profile")
    if isinstance(profile_claim, dict):
        candidate = profile_claim.get("profile") or profile_claim

    if candidate is None:
        unsafe = claims.get("unsafe_metadata") or {}
        if isinstance(unsafe, dict):
            candidate = unsafe.get("profile") or unsafe

    if not isinstance(candidate, dict):
        return None

    try:
        return CitizenProfile.model_validate(_normalize_keys(candidate))
    except Exception:  # noqa: BLE001 — tolerate odd shapes from FE
        log.warning("Could not parse profile from JWT claims", exc_info=True)
        return None


def _normalize_keys(d: dict[str, Any]) -> dict[str, Any]:
    """Accept FE camelCase keys by mapping to snake_case for our model."""
    rename = {
        "onboardingComplete": "onboarding_complete",
        "familySize": "family_size",
        "hasKids": "has_kids",
        "hasElderly": "has_elderly",
        "medicalConditions": "medical_conditions",
        "hasVehicle": "has_vehicle",
        "alternateShelter": "alternate_shelter",
    }
    return {rename.get(k, k): v for k, v in d.items()}


# ------------------------------------------------------------------ Dependency


def _bearer_token(request: Request) -> str:
    auth = request.headers.get("Authorization") or ""
    scheme, _, token = auth.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


async def get_current_user(request: Request) -> CurrentUser:
    """FastAPI dependency. Verifies the Clerk JWT and returns the citizen."""
    token = _bearer_token(request)
    claims = await verify_token(token)

    sub = claims.get("sub")
    if not isinstance(sub, str) or not sub:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "JWT missing `sub`")

    email = None
    email_claim = claims.get("email") or claims.get("email_address")
    if isinstance(email_claim, str):
        email = email_claim

    profile = _extract_profile(claims)

    return CurrentUser(clerk_user_id=sub, email=email, profile=profile)


# Optional version — does not 401 when the header is absent. Useful for routes
# that work for both authenticated and anonymous users.
async def get_optional_user(request: Request) -> CurrentUser | None:
    if not request.headers.get("Authorization"):
        return None
    try:
        return await get_current_user(request)
    except HTTPException:
        return None


__all__ = [
    "CitizenLocation",
    "CitizenProfile",
    "CurrentUser",
    "get_current_user",
    "get_optional_user",
    "verify_token",
]
