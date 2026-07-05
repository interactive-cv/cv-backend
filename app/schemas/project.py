from typing import Any

from pydantic import BaseModel


class ProjectLinkOut(BaseModel):
    label: str
    url: str


class ProjectOut(BaseModel):
    title: str
    period: str
    role: str
    tags: list[str] = []
    short_desc: str
    stack: list[str] = []
    metrics: dict[str, Any] = {}
    links: list[ProjectLinkOut] = []
    order_idx: int = 0
