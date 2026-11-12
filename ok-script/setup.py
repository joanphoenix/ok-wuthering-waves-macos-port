import os
import setuptools

os.environ["PYTHONIOENCODING"] = "utf-8"

VERSION_NUM = os.environ.get('OK_SCRIPT_BUILD_VERSION')
if VERSION_NUM:
    print(f'building explicit version {VERSION_NUM}')
else:
    try:
        from get_pypi_latest_version import GetPyPiLatestVersion

        obtainer = GetPyPiLatestVersion()
        latest_version = obtainer("ok-script")
        VERSION_NUM = obtainer.version_add_one(latest_version, add_patch=True)
        print(f'latest_version is {latest_version} new version is {VERSION_NUM}')
    except Exception:
        VERSION_NUM = "3.0.5b7+macos.1"

setuptools.setup(version=VERSION_NUM)
