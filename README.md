# qBittorrent Disk Guard

A simple daemon that monitors available disk space and pauses active qBittorrent downloads when available space drops below a configured threshold.

## Usage

### Docker

```shell
docker run -d \
  --name qbittorrent-disk-guard \
  --restart unless-stopped \
  -e QBITTORRENT_URL="http://qbittorrent:8080" \
  -e QBITTORRENT_API_KEY="qbt_xxxxxxxxxxxxxxxxxxxxxxxxxxxx" \
  -e FREE_SPACE_PATH="/downloads" \
  -e MIN_FREE_SPACE_GB="50" \
  -e ENABLE_AUTO_RESUME="true" \
  -v /path/to/downloads:/downloads:ro \
  ghcr.io/landerrosette/qbittorrent-disk-guard
```
