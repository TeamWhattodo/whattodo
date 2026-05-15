from datetime import datetime

from backend.connectors.base import BaseConnector
from backend.models import WorkItem


class SlackConnector(BaseConnector):
    async def fetch(self, since: datetime, until: datetime) -> list[WorkItem]:
        ...
