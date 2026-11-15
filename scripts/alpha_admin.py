"""Explicit local Alpha schema/account provisioning; passwords never passed on command line."""

import argparse
import getpass
from uuid import uuid4

from insureagent_api.config import Settings
from insureagent_api.modules.identity.auth import password_hash
from insureagent_persistence.store import Store, accounts
from sqlalchemy import insert


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["init", "create-user"])
    parser.add_argument("--username")
    args = parser.parse_args()
    settings = Settings.from_env()
    if settings is None:
        parser.error("Set ALPHA_DATA_KEY to a base64 32-byte encryption key first")
    store = Store(settings.database_url, settings.data_key)
    if args.command == "init":
        store.initialize()
        print("Alpha schema initialized; synthetic data only")
    else:
        if not args.username:
            parser.error("--username is required")
        password = getpass.getpass("Password (12-128 characters): ")
        if not 12 <= len(password) <= 128:
            parser.error("Password must be 12-128 characters")
        with store.transaction() as conn:
            conn.execute(
                insert(accounts).values(
                    id=str(uuid4()), username=args.username, password_hash=password_hash(password)
                )
            )
        print("Alpha account created")


if __name__ == "__main__":
    main()
