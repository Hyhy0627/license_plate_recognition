"""Artifact integrity and local runtime configuration regressions."""

from hashlib import sha256
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock

from botocore.response import StreamingBody
import pytest

from scripts import download_models
from src.config import settings
from src.core.models.registry import MODELS, PROJECT_ROOT, read_checksums
from src.core.models.runtime import create_model_runtime


def test_registered_artifacts_have_pinned_checksums():
    checksums = read_checksums(PROJECT_ROOT / "models/checksums.txt")
    assert {artifact.path for artifact in MODELS.values()} <= checksums.keys()
    config = MODELS["sequence-config"]
    bundled = (PROJECT_ROOT / config.bundled_path).read_bytes().replace(b"\r\n", b"\n")
    assert checksums[config.path] == sha256(bundled).hexdigest()


@pytest.mark.parametrize("source", [
    "https://example.com/releases/download/baseline-v1",
    "s3://alpr-models/baseline-v1",
])
def test_installer_only_replaces_after_verification(monkeypatch, tmp_path, source):
    artifact = MODELS["image-detector"]
    target = tmp_path / artifact.path
    contents = b"expected artifact"
    monkeypatch.setattr(download_models, "read_checksums", lambda _: {artifact.path: sha256(contents).hexdigest()})
    fetch = Mock(side_effect=lambda _, output: output.write(contents))
    monkeypatch.setattr(download_models, "fetch", fetch)
    with pytest.raises(ValueError, match="file missing"):
        download_models.install_models(("image-detector",), root=tmp_path, check=True)
    fetch.assert_not_called()
    download_models.install_models(("image-detector",), root=tmp_path, source_base=source)
    assert target.read_bytes() == contents
    assert fetch.call_args.args[0] == f"{source}/{target.name}"

    fetch.reset_mock()
    download_models.install_models(("image-detector",), root=tmp_path, source_base=source)
    fetch.assert_not_called()
    target.write_bytes(b"existing custom weights")
    fetch.side_effect = lambda _, output: output.write(b"wrong content")
    with pytest.raises(ValueError, match="downloaded checksum mismatch"):
        download_models.install_models(("image-detector",), root=tmp_path, source_base=source)
    assert target.read_bytes() == b"existing custom weights"
    assert list(target.parent.iterdir()) == [target]


def test_installer_streams_s3_artifact(monkeypatch):
    body = StreamingBody(BytesIO(b"weights"), 7)
    client = Mock()
    client.get_object.return_value = {"Body": body}
    monkeypatch.setattr("boto3.client", lambda _: client)
    output = BytesIO()
    download_models.fetch("s3://alpr-models/baseline%20v1/best.pt", output)
    client.get_object.assert_called_once_with(Bucket="alpr-models", Key="baseline v1/best.pt")
    client.close.assert_called_once()
    assert output.getvalue() == b"weights"


def test_local_runtime_validates_detector_file_before_loading(monkeypatch, tmp_path):
    checkpoint = tmp_path / "custom.pt"
    factory = Mock()
    monkeypatch.setattr(settings, "YOLO_MODEL_PATH", str(checkpoint))
    monkeypatch.setattr("src.core.image.detector.LicensePlateDetector", factory)
    runtime = create_model_runtime("local")
    with pytest.raises(RuntimeError, match="download_models.py"):
        runtime.image_detector()
    factory.assert_not_called()
    checkpoint.touch()
    assert runtime.image_detector() is factory.return_value
    assert Path(factory.call_args.kwargs["model_path"]) == checkpoint
