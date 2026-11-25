"""Serve private media from disk or stream byte ranges from object storage."""

from contextlib import closing
from datetime import timezone
from email.utils import format_datetime
from pathlib import Path
from secrets import token_hex

import anyio
from fastapi import Request
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse

from src.services.storage.base import RemoteFile


class _UnsatisfiableRange(ValueError):
    pass


def _parse_ranges(header: str, size: int) -> list[tuple[int, int]]:
    units, separator, requested = header.partition("=")
    if not separator:
        raise ValueError("Malformed range header.")
    if units.strip().lower() != "bytes":
        raise ValueError("Only support bytes range")
    if requested.count(",") >= 100:
        return []

    ranges = []
    for part in requested.split(","):
        first, separator, last = part.strip().partition("-")
        first, last = first.strip(), last.strip()
        if not separator or not (first or last):
            continue
        try:
            start = int(first) if first else max(size - int(last), 0)
            end = min(int(last) + 1, size) if first and last else size
        except ValueError:
            continue
        ranges.append((start, end))

    if not ranges:
        raise ValueError("Range header: range must be requested")
    if any(not 0 <= start < size for start, _ in ranges):
        raise _UnsatisfiableRange
    if any(start >= end for start, end in ranges):
        raise ValueError("Range header: start must be less than end")

    merged = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1]:
            previous_start, previous_end = merged[-1]
            merged[-1] = (previous_start, max(previous_end, end))
        else:
            merged.append((start, end))
    return merged


def _read_object(media, byte_range=None):
    with closing(media.open(byte_range)) as stream:
        while chunk := stream.read(64 * 1024):
            yield chunk


def _multipart_object(media, parts, closing_boundary):
    for header, byte_range, _ in parts:
        yield header
        yield from _read_object(media, byte_range)
        yield b"\r\n"
    yield closing_boundary


class _ObjectResponse(StreamingResponse):
    def __init__(self, chunks, **response_options):
        super().__init__(chunks, **response_options)
        self.chunks = chunks

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            # An interrupted HTTP download must release the S3 body connection.
            with anyio.CancelScope(shield=True):
                await anyio.to_thread.run_sync(self.chunks.close)


def media_response(request: Request, media: Path | RemoteFile, media_type: str):
    headers = {"Cache-Control": "no-store"}
    if isinstance(media, Path):
        return FileResponse(media, media_type=media_type, headers=headers)

    headers.update({
        "Accept-Ranges": "bytes",
        "Content-Length": str(media.size),
        "ETag": media.etag,
        "Last-Modified": format_datetime(media.last_modified.astimezone(timezone.utc), usegmt=True),
    })
    requested = request.headers.get("range")
    if_range = request.headers.get("if-range")
    ranges = []
    if requested is not None and (if_range is None or if_range in (headers["ETag"], headers["Last-Modified"])):
        try:
            ranges = _parse_ranges(requested, media.size)
        except _UnsatisfiableRange:
            return PlainTextResponse(status_code=416, headers={"Content-Range": f"bytes */{media.size}"})
        except ValueError as exc:
            return PlainTextResponse(str(exc), status_code=400)

    if not ranges:
        return _ObjectResponse(_read_object(media), media_type=media_type, headers=headers)
    if len(ranges) == 1:
        start, end = ranges[0]
        headers["Content-Range"] = f"bytes {start}-{end - 1}/{media.size}"
        headers["Content-Length"] = str(end - start)
        return _ObjectResponse(_read_object(media, f"bytes={start}-{end - 1}"),
                               status_code=206, media_type=media_type, headers=headers)

    boundary = token_hex(13)
    parts = [
        (
            f"--{boundary}\r\nContent-Type: {media_type}\r\n"
            f"Content-Range: bytes {start}-{end - 1}/{media.size}\r\n\r\n".encode("ascii"),
            f"bytes={start}-{end - 1}",
            end - start,
        )
        for start, end in ranges
    ]
    final = f"--{boundary}--\r\n".encode("ascii")
    headers["Content-Length"] = str(sum(len(part) + size + 2 for part, _, size in parts) + len(final))
    return _ObjectResponse(_multipart_object(media, parts, final), status_code=206,
                           media_type=f"multipart/byteranges; boundary={boundary}", headers=headers)
