"""
LocalSub - Windows Build & Packaging Script.
Executes PyInstaller, verifies output integrity, generates distribution ZIP, and produces SHA-256.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
VERSION = "1.0.0"
ZIP_NAME = f"LocalSub-v{VERSION}-windows-x64.zip"


def calculate_sha256(file_path: Path) -> str:
    """Compute SHA-256 checksum of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def build() -> None:
    print(f"=== Starting LocalSub v{VERSION} Windows Build ===")
    os.chdir(PROJECT_ROOT)

    spec_file = PROJECT_ROOT / "packaging" / "LocalSub.spec"
    if not spec_file.is_file():
        raise FileNotFoundError(f"Spec file not found at: {spec_file}")

    # Run PyInstaller
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        str(spec_file),
        "--noconfirm",
        "--clean",
    ]
    print(f"Executing: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

    out_dir = DIST_DIR / "LocalSub"
    exe_file = out_dir / "LocalSub.exe"

    if not exe_file.is_file():
        raise RuntimeError(f"PyInstaller build failed: Expected executable not found at '{exe_file}'")

    print(f"Executable built successfully: {exe_file}")

    # Ensure icons and notices are copied to output directory
    assets_src = PROJECT_ROOT / "assets"
    if assets_src.is_dir():
        for target_assets in [out_dir / "assets", out_dir / "_internal" / "assets"]:
            target_assets.parent.mkdir(parents=True, exist_ok=True)
            if target_assets.exists():
                shutil.rmtree(target_assets)
            shutil.copytree(assets_src, target_assets)

    for doc in ["LICENSE", "THIRD_PARTY_NOTICES.md", "README.md"]:
        doc_path = PROJECT_ROOT / doc
        if doc_path.is_file():
            shutil.copy2(doc_path, out_dir / doc)

    # Create ZIP archive
    zip_path = DIST_DIR / ZIP_NAME
    if zip_path.exists():
        zip_path.unlink()

    print(f"Creating release archive: {zip_path.name}...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, _, files in os.walk(out_dir):
            for file in files:
                file_path = Path(root) / file
                archive_name = file_path.relative_to(DIST_DIR)
                zf.write(file_path, str(archive_name))

    zip_size_mb = zip_path.stat().st_size / (1024 * 1024)
    sha256_hash = calculate_sha256(zip_path)

    # Write checksum file
    checksum_file = DIST_DIR / f"{ZIP_NAME}.sha256"
    checksum_file.write_text(f"{sha256_hash}  {ZIP_NAME}\n", encoding="utf-8")

    print("\n" + "=" * 60)
    print("BUILD AND PACKAGING COMPLETED SUCCESSFULLY!")
    print(f"  Distribution ZIP : {zip_path}")
    print(f"  Archive Size     : {zip_size_mb:.2f} MB")
    print(f"  SHA-256 Checksum : {sha256_hash}")
    print(f"  Checksum File    : {checksum_file}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    build()
