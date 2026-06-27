from pydantic import BaseModel


class ProjectOut(BaseModel):
    title: str
    period: str
    role: str
    tags: list[str] = []
    short_desc: str
    stack: list[str] = []
    metrics: dict = {}
    order_idx: int = 0
