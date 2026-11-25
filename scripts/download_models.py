"""Install the baseline model set from verified local, HTTPS or S3 artifacts."""

import argparse
from contextlib import closing
from http.client import HTTPException
import os
from pathlib import Path
import shutil
import sys
from tempfile import NamedTemporaryFile
from urllib.error import HTTPError
from urllib.parse import quote, unquote, urlsplit, urlunsplit
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.models.registry import (
    IMAGE_MODELS, MODELS, MODEL_SET_VERSION, PROJECT_ROOT, VIDEO_MODELS,
    ModelArtifact, file_sha256, read_checksums,
)


GROUPS = {
    "all": (*IMAGE_MODELS, *VIDEO_MODELS),
    "image": IMAGE_MODELS,
    "video": VIDEO_MODELS,
}


def source_url(base: str | None, artifact: ModelArtifact) -> str | None:
    if not base:
        return artifact.url
    source = urlsplit(base)
    if (source.scheme not in {"s3", "https"} or not source.hostname
            or source.username or source.password or source.query or source.fragment):
        raise ValueError("Model source must be an HTTPS release directory or s3://bucket/prefix")
    path = source.path.rstrip("/") + "/" + quote(Path(artifact.path).name)
    return urlunsplit(source._replace(path=path))


def fetch(url: str, output) -> None:
    source = urlsplit(url)
    if source.scheme == "s3":
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError

        try:
            with closing(boto3.client("s3")) as client:
                with closing(client.get_object(Bucket=source.netloc, Key=unquote(source.path.lstrip("/")))["Body"]) as body:
                    shutil.copyfileobj(body, output)
        except (BotoCoreError, ClientError) as exc:
            raise ValueError(f"S3 transfer failed ({type(exc).__name__})") from None
        return

    try:
        with urlopen(url, timeout=60) as response:
            if urlsplit(response.geturl()).scheme != "https":
                raise ValueError("The artifact source redirected away from HTTPS")
            shutil.copyfileobj(response, output)
    except HTTPError as exc:
        raise ValueError(f"Artifact download failed (HTTP {exc.code})") from None
    except (OSError, HTTPException) as exc:
        raise ValueError(f"Artifact download failed ({type(exc).__name__})") from None


def install_models(model_ids, *, source_base=None, check=False, root=PROJECT_ROOT) -> None:
    checksums = read_checksums(PROJECT_ROOT / "models/checksums.txt")
    missing_checksums = [model_id for model_id in model_ids if MODELS[model_id].path not in checksums]
    if missing_checksums:
        raise ValueError(f"Missing checksums for {', '.join(missing_checksums)}")

    errors = []
    for model_id in model_ids:
        artifact = MODELS[model_id]
        target = root / artifact.path
        expected = checksums[artifact.path]
        try:
            present = target.is_file()
            if present and file_sha256(target) == expected:
                print(f"Verified {artifact.path}")
                continue
            if check:
                raise ValueError("checksum mismatch" if present else "file missing")

            url = source_url(source_base, artifact) if not artifact.bundled_path else None
            if not (url or artifact.bundled_path):
                raise ValueError("no default download source, set --source-base or ALPR_MODEL_SOURCE")
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = None
            try:
                with NamedTemporaryFile(dir=target.parent, suffix=".download", delete=False) as output:
                    temporary = Path(output.name)
                    if artifact.bundled_path:
                        config = (PROJECT_ROOT / artifact.bundled_path).read_bytes().replace(b"\r\n", b"\n")
                        output.write(config)
                    else:
                        print(f"Downloading {artifact.path}", flush=True)
                        fetch(url, output)
                if file_sha256(temporary) != expected:
                    raise ValueError("downloaded checksum mismatch")
                temporary.replace(target)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
            print(f"Installed {artifact.path}")
        except (ValueError, OSError) as exc:
            errors.append(f"{artifact.path}: {exc}")

    if errors:
        raise ValueError("\n".join(errors))


def main(argv=None, *, default_models=GROUPS["all"]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", choices=GROUPS, help="Install one runtime model group")
    parser.add_argument("--artifact", choices=MODELS, action="append", help="Select an artifact (repeatable)")
    parser.add_argument("--source-base", default=os.environ.get("ALPR_MODEL_SOURCE"),
                        help="HTTPS release directory or s3://bucket/prefix containing the artifact filenames")
    parser.add_argument("--check", action="store_true", help="Only verify, without modifying files or using the network")
    args = parser.parse_args(argv)
    models = list(dict.fromkeys((*GROUPS.get(args.group, ()), *(args.artifact or ())))) or default_models
    print(f"Model set {MODEL_SET_VERSION}")
    try:
        install_models(models, source_base=args.source_base, check=args.check)
    except (ValueError, OSError) as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
