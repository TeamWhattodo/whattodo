from abc import ABC, abstractmethod
from datetime import datetime

from backend.models import WorkItem


class BaseConnector(ABC):
    @abstractmethod
    async def fetch(self, since: datetime, until: datetime) -> list[WorkItem]:
        """부재 기간 항목 수집. tools/fetch.py 에서 호출됨."""
        ...
