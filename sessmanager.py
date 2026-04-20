import hashlib
import time
import requests
import json
from pydantic import BaseModel, ConfigDict, Field
from typing import Dict, Optional
from models import BusquedaNormaRequest

class SearchSessionState(BaseModel):
    session: requests.Session
    total_pags: Optional[int] = None
    created_at: float = Field(default_factory=time.time)
    first_request: bool = True
    model_config = ConfigDict(arbitrary_types_allowed=True)


class SessionManager:
    def __init__(self):
        self.globsess: requests.Session = None
        self.globtimestamp: int = None
        self.active_searches: Dict[str, SearchSessionState] = {}
        self.ttl = 300

    def _key(self, request: BusquedaNormaRequest) -> str:
        return hashlib.md5(
            json.dumps(request.model_dump(exclude_none=True), sort_keys=True).encode()
        ).hexdigest()

    def get_session(self) -> requests.Session:
        now = int(time.time())
        is_new = self.globtimestamp is None
        is_expired = not is_new and (now - self.globtimestamp) > self.ttl
        if is_expired:
            self.globsess.close()
            
        if is_new or is_expired:
            self.globsess = requests.Session()
            self.globtimestamp = now
        return self.globsess

    def close_expired(self):
        delete_keys = []
        for k in self.active_searches:
            val = self.active_searches[k]
            now = int(time.time())
            if (now - val.created_at) > self.ttl:
                val.session.close()
                delete_keys.append(k)
        for k in delete_keys:
            del self.active_searches[k]

    def get_search_session(self, request: BusquedaNormaRequest) -> Optional[SearchSessionState]:
        self.close_expired()
        key = self._key(request)
        if key not in self.active_searches:
            state = SearchSessionState(session=requests.Session())
            self.active_searches[key] = state
            return state
        else:
            return self.active_searches[key]

    def put_pages_count(self, request: BusquedaNormaRequest, page_count: int):
        key = self._key(request)
        if key not in self.active_searches:
            raise ValueError("la sesión ya deberia existir para esta llamada")
        else:
            old_state = self.active_searches[key]
            new_state = SearchSessionState(
                session=old_state.session,
                created_at=old_state.created_at,
                total_pags=page_count,
                first_request=False,
            )
            self.active_searches[key] = new_state
