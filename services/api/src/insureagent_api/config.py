import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    data_key: str

    @classmethod
    def from_env(cls):
        key = os.environ.get("ALPHA_DATA_KEY", "")
        if not key:
            return None
        return cls(os.environ.get("DATABASE_URL", "sqlite:///alpha.db"), key)
