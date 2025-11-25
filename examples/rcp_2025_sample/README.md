# RCP 2025 sample package

This folder documents the shape of a generated RCP 2025 package without checking binary payloads into source control.
Run the helper script to produce a full sample locally:

```bash
PYTHONPATH=src python examples/generate_sample.py
```

The script writes the following files:

- `manifest.json` – package metadata
- `index.json` – channel counts and duration
- `channels/touch.pbz` – touch trajectory columnar data (zstd-compressed protobuf)
- `channels/acc.pbz` – accelerometer columnar data
- `channels/gyro.pbz` – gyroscope columnar data
- `checksums.txt` – SHA-256 checksums for the files above

A generated manifest resembles:

```json
{
  "version": "rcp_2025",
  "package_id": "sample-uuid",
  "source": "demo/calligraphy",
  "device_profile": "pixel_4",
  "dpi": 320.0,
  "created_at": "2025-05-06T07:08:09Z",
  "attributes": {"style": "demo", "author": "cloud_readers"}
}
```

The accompanying index mirrors the written channels:

```json
{
  "touch_samples": 4,
  "acc_samples": 4,
  "gyro_samples": 4,
  "duration_seconds": 0.06,
  "checksums": {
    "manifest.json": "<sha256>",
    "index.json": "<sha256>",
    "channels/touch.pbz": "<sha256>",
    "channels/acc.pbz": "<sha256>",
    "channels/gyro.pbz": "<sha256>"
  }
}
```
