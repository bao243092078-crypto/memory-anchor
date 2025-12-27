"""API auth helpers."""

from __future__ import annotations

import os
from typing import Optional

from fastapi import Header, HTTPException, status


def _extract_bearer(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


def verify_api_key(
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> None:
    """
    Simple API key auth for /api routes.

    If MA_API_KEY is not set, auth is disabled for local/dev usage.
    """
    expected = os.getenv("MA_API_KEY")
    if not expected:
        return

    token = x_api_key or _extract_bearer(authorization)
    if token != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
