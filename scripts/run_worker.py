"""Poll authoritative Alpha jobs; no external messages or model calls."""

import argparse
import time

from insureagent_ai.extraction.model import configured_extract
from insureagent_api.config import Settings
from insureagent_persistence.store import Store
from insureagent_worker.processor import Processor


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    settings = Settings.from_env()
    if settings is None:
        parser.error("Set ALPHA_DATA_KEY and initialize the database first")
    worker = Processor(
        Store(settings.database_url, settings.data_key), extractor=configured_extract
    )
    if args.once:
        worker.run_once()
        return
    try:
        while True:
            if not worker.run_once():
                time.sleep(1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
