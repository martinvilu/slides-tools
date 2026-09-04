import json
from pathlib import Path
import zipfile
import pytest

from slide_tools.packer import package_extension


def test_package_slide_extension(tmp_path):
    res = package_extension(output_dir=tmp_path, target="both")

    assert "chrome" in res
    assert "firefox" in res

    chrome_zip = res["chrome"]
    firefox_xpi = res["firefox"]

    assert chrome_zip.exists()
    assert firefox_xpi.exists()

    # Verificar Chrome zip
    with zipfile.ZipFile(chrome_zip, "r") as zf:
        namelist = zf.namelist()
        assert "manifest.json" in namelist
        assert "background.js" in namelist
        assert "content-present.js" in namelist
        assert "content-speaker.js" in namelist
        assert "overlay.css" in namelist
        assert "popup.html" in namelist

        chrome_manifest = json.loads(zf.read("manifest.json"))
        assert chrome_manifest["manifest_version"] == 3
        assert chrome_manifest["background"]["service_worker"] == "background.js"
        assert "browser_specific_settings" not in chrome_manifest

    # Verificar Firefox xpi
    with zipfile.ZipFile(firefox_xpi, "r") as zf:
        namelist = zf.namelist()
        assert "manifest.json" in namelist
        assert "background.js" in namelist

        ff_manifest = json.loads(zf.read("manifest.json"))
        assert ff_manifest["manifest_version"] == 3
        assert ff_manifest["background"]["scripts"] == ["background.js"]
        assert "browser_specific_settings" in ff_manifest
        assert ff_manifest["browser_specific_settings"]["gecko"]["id"] == "slide-bridge@local.dev"
        assert ff_manifest["browser_specific_settings"]["gecko"]["data_collection_permissions"]["required"] == ["none"]
