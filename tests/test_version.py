import re
from os.path import relpath
from pathlib import Path

from notifications_utils import version


def test_changelog_matches_latest_version():
    changelog = Path("CHANGELOG.md")
    versions = [line.strip(" #") for line in changelog.read_text().splitlines() if re.match(r"## \d+\.\d+\.\d+$", line)]
    version_file_path = relpath(Path(version.__file__).resolve(), Path(".").resolve())
    assert versions[0] == version.__version__, (
        f"Mismatched version numbers\n"
        f"• {versions[0]} in {changelog.relative_to('.')}\n"
        f"• {version.__version__} in {version_file_path}\n"
    )
