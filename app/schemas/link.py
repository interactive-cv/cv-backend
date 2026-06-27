from datetime import datetime

from pydantic import BaseModel


class LinkResolveOut(BaseModel):
    cv_variant_slug: str
    expires_at: datetime


class LinkCreateIn(BaseModel):
    cv_variant_slug: str
    ttl_days: int = 7
    max_hits: int | None = None
