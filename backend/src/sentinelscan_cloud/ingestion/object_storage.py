"""
Object storage abstraction for raw report archival (Section 11 step 7,
Section 7: "S3-compatible blob storage").

The interface is deliberately narrow (put/get by key) so swapping the
backend is a deployment decision (Section 16), not an architectural
one -- exactly the same reasoning already applied to the
narrative-generation component in Section 12.4. `LocalFilesystemObjectStorage`
is a real, fully-working implementation (not a mock) suitable for local
development and for this sandbox, where no real S3-compatible service
is reachable; `S3ObjectStorage` is provided as the production
implementation's shape, using boto3, which is not installed in this
sandbox (see Stage 3 Completion Report) but requires no code changes
elsewhere to swap in -- only which class get_object_storage() returns.
"""
from __future__ import annotations

import pathlib
from typing import Protocol

from sentinelscan_cloud.config.settings import get_settings


class ObjectStorage(Protocol):
    def put(self, key: str, data: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...


class LocalFilesystemObjectStorage:
    """Real, working implementation backed by a local directory. Used
    whenever OBJECT_STORAGE_ENDPOINT is unset (local dev, tests, and
    this sandbox) -- never silently used in a real deployment, since
    Settings.object_storage_endpoint being unset is itself the signal."""

    def __init__(self, root: pathlib.Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, key: str) -> pathlib.Path:
        # Reject any key that could escape `root` via path traversal --
        # a Report's raw_blob_storage_key must never be usable to write
        # or read outside the storage root (Section 15: treat all
        # ingested/derived values as untrusted).
        candidate = (self.root / key).resolve()
        if self.root.resolve() not in candidate.parents and candidate != self.root.resolve():
            raise ValueError(f"storage key {key!r} resolves outside the storage root")
        return candidate

    def put(self, key: str, data: bytes) -> None:
        path = self._path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key: str) -> bytes:
        return self._path_for(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path_for(key).exists()


class S3ObjectStorage:
    """Production implementation shape (Section 7, Section 16: any
    S3-compatible managed service). Requires `boto3`, which is not
    installed in this sandbox -- see Stage 3 Completion Report,
    "Environment Blocked". Not executed or unit-tested here; included
    so the interface's real shape is committed now rather than
    invented later."""

    def __init__(self, bucket: str, endpoint_url: str | None = None):
        import boto3  # noqa: F401 -- deferred import: only required if this class is actually used

        self._bucket = bucket
        self._client = boto3.client("s3", endpoint_url=endpoint_url)

    def put(self, key: str, data: bytes) -> None:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data)

    def get(self, key: str) -> bytes:
        response = self._client.get_object(Bucket=self._bucket, Key=key)
        return response["Body"].read()

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except self._client.exceptions.ClientError:
            return False


_object_storage: ObjectStorage | None = None


def get_object_storage() -> ObjectStorage:
    global _object_storage
    if _object_storage is None:
        settings = get_settings()
        if settings.object_storage_endpoint:
            _object_storage = S3ObjectStorage(
                bucket=settings.object_storage_bucket, endpoint_url=settings.object_storage_endpoint
            )
        else:
            _object_storage = LocalFilesystemObjectStorage(pathlib.Path.cwd() / ".data" / "reports")
    return _object_storage
