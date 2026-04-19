# no es óptimo es básicamente un Redis en código,
# para no reinventar la rueda es mejor que la implementación 
# use una instancia independiente de Redis y guarde las cookies

from dataclasses import dataclass, field
import time
import hashlib
import requests
import json
from models import BusquedaNormaRequest, BusquedaNormaResponse
from typing import Optional


@dataclass
class CachedSearch:
    session: requests.Session
    result: BusquedaNormaResponse
    total_pags: int
    current_page: int = 1
    created_at: float = field(default_factory=time.time)

    def is_expired(self, ttl: int) -> bool:
        return time.time() - self.created_at > ttl

class SearchCache:
    def __init__(self, ttl: int = 300, max_size: int = 100):
        self.ttl = ttl
        self.max_size = max_size
        self._cache: dict[str, CachedSearch] = {}

    def _key(self, request: BusquedaNormaRequest) -> str:
        return hashlib.md5(
            json.dumps(request.model_dump(exclude_none=True), sort_keys=True).encode()
        ).hexdigest()

    def get(self, request: BusquedaNormaRequest) -> Optional[CachedSearch]:
        cached = self._cache.get(self._key(request))
        if cached and not cached.is_expired(self.ttl):
            return cached
        return None

    def set(self, request: BusquedaNormaRequest, value: CachedSearch) -> None:
        self._cleanup()
        self._cache[self._key(request)] = value

    def _cleanup(self) -> None:
        self._cache = {k: v for k, v in self._cache.items() if not v.is_expired(self.ttl)}
        if len(self._cache) >= self.max_size:
            sorted_keys = sorted(self._cache, key=lambda k: self._cache[k].created_at)
            for key in sorted_keys[:len(self._cache) - self.max_size + 1]:
                del self._cache[key]

