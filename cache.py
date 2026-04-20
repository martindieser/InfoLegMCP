import hashlib
import json
from pydantic import BaseModel
from typing import Optional
import diskcache
from models import BusquedaNormaRequest, BusquedaNormaResponse, VerNormaResponse



class PageCache:
    def __init__(self, directory: str = ".cache/pages", ttl: int = 3000):
        self.ttl = ttl
        self._cache = diskcache.Cache(directory)

    def _key(self, request: BusquedaNormaRequest, page: int) -> str:
        base = hashlib.md5(
            json.dumps(request.model_dump(exclude_none=True), sort_keys=True).encode()
        ).hexdigest()
        return f"{base}_{page}"

    def get(self, request: BusquedaNormaRequest, page: int) -> Optional[BusquedaNormaResponse]:
        return self._cache.get(self._key(request, page))

    def set(self, request: BusquedaNormaRequest, page: int, result: BusquedaNormaResponse) -> None:
        self._cache.set(self._key(request, page), result, expire=self.ttl)

    def close(self):
        self._cache.close()

class NormaCache:
    def __init__(self, directory: str = ".cache/normas", ttl: int = 86400):
        self.ttl = ttl
        self._cache = diskcache.Cache(directory)

    def get(self, id: int) -> Optional[VerNormaResponse]:
        return self._cache.get(str(id))

    def set(self, id: int, result: VerNormaResponse) -> None:
        self._cache.set(str(id), result, expire=self.ttl)

    def close(self):
        self._cache.close()
