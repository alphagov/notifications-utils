import pathlib
from base64 import b64decode
from importlib import resources as importlib_resources
from importlib.metadata import version

import requests

requirements_file = pathlib.Path("requirements.in")
frozen_requirements_file = pathlib.Path("requirements.txt")
repo_name = "alphagov/notifications-utils"
config_files = {
    filename: importlib_resources.files("notifications_utils.version_tools").joinpath(filename).read_bytes()
    for filename in (
        "ruff.toml",
        "requirements_for_test_common.in",
        ".pre-commit-config.yaml",
    )
}


class color:
    PURPLE = "\033[95m"
    CYAN = "\033[96m"
    DARKCYAN = "\033[36m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    END = "\033[0m"


def upgrade_version():
    current_version = get_app_version()
    newest_version = get_remote_version()

    write_version_to_requirements_file(newest_version)

    print(  # noqa: T201
        f"{color.GREEN}✅ {color.BOLD}notifications-utils bumped to {newest_version}{color.END}\n\n"
        f"{color.YELLOW}{color.UNDERLINE}Now run:{color.END}\n\n"
        f"  make freeze-requirements\n"
        f"  git add requirements* && git commit\n\n"
        f"{color.YELLOW}{color.UNDERLINE}Suggested commit message:{color.END}\n\n"
        f"Bump utils to {newest_version}\n\n"
        f"{get_relevant_changelog_lines(current_version, newest_version)}\n***\n\n"
        f"Complete changes: https://github.com/{repo_name}/compare/{current_version}...{newest_version}\n"
    )


def get_remote_version():
    exec(get_file_contents_from_github("main", "notifications_utils/version.py"))
    return locals()["__version__"]


def get_app_version():
    return version("notifications_utils")


def write_version_to_requirements_file(version):
    def replace_line(line):
        if repo_name in line:
            return f"notifications-utils @ git+https://github.com/{repo_name}.git@{version}\n"
        return line

    if requirements_file.exists():
        requirements_file_to_modify = requirements_file
    else:
        requirements_file_to_modify = frozen_requirements_file

    new_requirements_file_contents = "".join(
        replace_line(line) for line in requirements_file_to_modify.read_text().splitlines(True)
    )

    requirements_file_to_modify.write_text(new_requirements_file_contents)


def get_relevant_changelog_lines(current_version, newest_version):
    old_changelog, new_changelog = (
        get_file_contents_from_github(version, "CHANGELOG.md") for version in (current_version, newest_version)
    )

    # Insert a space before `##` so that if copy/pasted into a git commit message, they aren't considered comments (by
    # eg vim), but still render as markdown the same way (as headings).
    new_changelog = new_changelog.replace("\n##", "\n ##")

    lines_added = new_changelog.count("\n") - old_changelog.count("\n")
    header_lines = new_changelog.split("##")[0].count("\n")

    return "\n".join(new_changelog.split("\n")[header_lines : header_lines + lines_added])


def get_file_contents_from_github(branch_or_tag, path) -> str:
    response = requests.get(f"https://api.github.com/repos/{repo_name}/contents/{path}?ref={branch_or_tag}")
    response.raise_for_status()
    return b64decode(response.json()["content"]).decode(encoding="utf-8")


def copy_config():
    local_utils_version = get_app_version()
    for filename, file_bytes in config_files.items():
        # writing as raw bytes because we want to remain as faithful to original as possible
        with open(filename, "wb") as f:
            f.write(
                f"# This file was automatically copied from notifications-utils@{local_utils_version}\n\n".encode(
                    "ascii"
                )
            )
            f.write(file_bytes)
