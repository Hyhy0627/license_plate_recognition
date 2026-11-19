"""Install only EasyOCR's small line-recognition weights in the project.

Run explicitly with --download. Application requests never download models.
"""
import argparse
import hashlib
import io
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download', action='store_true')
    args = parser.parse_args()
    from easyocr.config import recognition_models
    spec = recognition_models['gen2']['english_g2']
    folder = ROOT / 'models' / 'easyocr'
    target = folder / spec['filename']
    if target.exists():
        data = target.read_bytes()
    elif args.download:
        import requests
        response = requests.get(spec['url'], timeout=(10, 60))
        response.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            # Read only the expected member; never extract arbitrary zip paths.
            data = archive.read(spec['filename'])
        if hashlib.md5(data).hexdigest() != spec['md5sum']:
            raise RuntimeError('Downloaded model checksum does not match the installed EasyOCR metadata')
        folder.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    else:
        raise SystemExit('Model missing. Run this script with --download to install it explicitly.')
    if hashlib.md5(data).hexdigest() != spec['md5sum']:
        raise RuntimeError('Existing model checksum mismatch; file was not replaced')
    print(f'Model: {target}\nBytes: {len(data)}\nSHA256: {hashlib.sha256(data).hexdigest()}')


if __name__ == '__main__':
    main()
