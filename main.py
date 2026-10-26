#!/usr/bin/env python3

import logging
import os
import shutil
import sys
import time

import httpx

QBITTORRENT_URL = os.getenv("QBITTORRENT_URL", "http://localhost:8080")
QBITTORRENT_API_KEY = os.getenv("QBITTORRENT_API_KEY")
FREE_SPACE_PATH = os.getenv("FREE_SPACE_PATH")
MIN_FREE_SPACE_GB = os.getenv("MIN_FREE_SPACE_GB")
ENABLE_AUTO_RESUME = os.getenv("ENABLE_AUTO_RESUME", "false").lower() == "true"
CHECK_INTERVAL = 10

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)


def validate_env():
    missing = []
    if QBITTORRENT_API_KEY is None:
        missing.append("QBITTORRENT_API_KEY")
    if FREE_SPACE_PATH is None:
        missing.append("FREE_SPACE_PATH")
    if MIN_FREE_SPACE_GB is None:
        missing.append("MIN_FREE_SPACE_GB")

    if missing:
        for env_var in missing:
            logging.error(
                f"{env_var} is not set. Please set it in the environment variables."
            )
        raise ValueError("Missing required environment variables.")

    if float(MIN_FREE_SPACE_GB) < 0:
        raise ValueError("MIN_FREE_SPACE_GB must be a non-negative number.")


def get_free_space_gb(path: str) -> float:
    return shutil.disk_usage(path).free / (1024 * 1024 * 1024)


def from_tags_str(tags_str: str) -> set[str]:
    return {tag.strip() for tag in tags_str.split(",") if tag.strip()}


def to_hashes_str(hashes: list[str]) -> str:
    return "|".join(hashes)


def main():
    try:
        validate_env()
    except ValueError as e:
        logging.error(e)
        sys.exit(1)

    client = httpx.Client(
        base_url=f"{QBITTORRENT_URL}/api/v2",
        headers={"Authorization": f"Bearer {QBITTORRENT_API_KEY}"},
    )
    min_free_space_gb = float(MIN_FREE_SPACE_GB)

    while True:
        try:
            response = client.get("/torrents/info")
            response.raise_for_status()
            torrents = response.json()

            if get_free_space_gb(FREE_SPACE_PATH) < min_free_space_gb:
                to_pause = [
                    torrent["hash"]
                    for torrent in torrents
                    if torrent["state"]
                    in (
                        "allocating",
                        "downloading",
                        "metaDL",
                        "queuedDL",
                        "stalledDL",
                        "checkingDL",
                    )
                ]
                if to_pause:
                    client.post(
                        "/torrents/stop", data={"hashes": to_hashes_str(to_pause)}
                    )
                    client.post(
                        "/torrents/addTags",
                        data={
                            "hashes": to_hashes_str(to_pause),
                            "tags": "disk_space_paused",
                        },
                    )
                    logging.info(
                        f"Paused {len(to_pause)} torrent{'s' if len(to_pause) != 1 else ''} due to low disk space."
                    )
            elif ENABLE_AUTO_RESUME:
                to_resume = [
                    torrent["hash"]
                    for torrent in torrents
                    if "disk_space_paused" in from_tags_str(torrent["tags"])
                    and torrent["state"] in ("stoppedDL",)
                ]
                if to_resume:
                    client.post(
                        "/torrents/start", data={"hashes": to_hashes_str(to_resume)}
                    )
                    client.post(
                        "/torrents/removeTags",
                        data={
                            "hashes": to_hashes_str(to_resume),
                            "tags": "disk_space_paused",
                        },
                    )
                    logging.info(
                        f"Resumed {len(to_resume)} torrent{'s' if len(to_resume) != 1 else ''} as disk space is sufficient."
                    )

            user_resumed = [
                torrent["hash"]
                for torrent in torrents
                if "disk_space_paused" in from_tags_str(torrent["tags"])
                and torrent["state"] not in ("stoppedDL",)
            ]
            if user_resumed:
                client.post(
                    "/torrents/removeTags",
                    data={
                        "hashes": to_hashes_str(user_resumed),
                        "tags": "disk_space_paused",
                    },
                )
                logging.info(
                    f"Untagged {len(user_resumed)} torrent{'s' if len(user_resumed) != 1 else ''} resumed by user action."
                )
        except httpx.HTTPError as e:
            logging.warning(f"Failed to communicate with qBittorrent: {e}")
        except Exception as e:
            logging.error(e)

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
