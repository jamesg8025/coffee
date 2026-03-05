"""
Admin endpoints for managing blocked IPs.

All endpoints require ADMIN role — a CONSUMER or ROASTER gets 403.

These endpoints give the security team visibility into the rate limiter
state stored in Redis without needing direct Redis access.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import CurrentUser, require_role
from app.rate_limiter import clear_block, list_blocked
from app.redis_client import get_redis
from app.schemas.security import BlockedIPEntry, UnblockResponse

router = APIRouter()


@router.get("", response_model=list[BlockedIPEntry])
async def list_blocked_ips(
    _: CurrentUser = Depends(require_role("ADMIN")),
):
    """
    Return all currently blocked IPs and their remaining TTL.
    Reads directly from Redis — reflects live state.
    """
    redis = get_redis()
    return await list_blocked(redis)


@router.delete("/{ip}", response_model=UnblockResponse)
async def unblock_ip(
    ip: str,
    _: CurrentUser = Depends(require_role("ADMIN")),
):
    """
    Manually unblock an IP address.
    Removes the block key and clears the failure history from Redis.
    """
    redis = get_redis()
    was_blocked = await clear_block(redis, ip)
    if not was_blocked:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"IP {ip!r} is not currently blocked.",
        )
    return UnblockResponse(ip=ip, unblocked=True)
