import os
import shutil
from pathlib import Path

from oarepo_cli.config import MonorepoConfig
from oarepo_cli.utils import check_call
from oarepo_cli.watch import copy_watched_paths, load_watched_paths

# Taken from Invenio-cli
#
# this and the following were taken from:
# https://github.com/inveniosoftware/invenio-cli/blob/0a49d438dc3c5ace872ce27f8555b401c5afc6e7/invenio_cli/commands/local.py#L45
# and must be called from the site directory
#
# The reason is that symlinking functionality is only part of invenio-cli
# and that is dependent on pipenv, which can not be used inside alpine
# (because we want to keep the image as small as possible, we do not install gcc
# and can only use compiled native python packages - like cairocffi or uwsgi). The
# version of these provided in alpine is slightly lower than the one created by Pipenv
# - that's why we use plain invenio & pip here.
#
# Another reason is that invenio-cli is inherently unstable when non-rdm version
# is used - it gets broken with each release.


def build_assets(*, cfg: MonorepoConfig, site, **kwargs):
    site_dir = cfg.project_dir / site["site_dir"]
    invenio = os.environ.get(
        "INVENIO_INSTANCE_PATH", site_dir / ".venv" / "var" / "instance"
    )
    if not isinstance(invenio, Path):
        invenio = Path(invenio)

    pdm_name = site["pdm_name"]

    shutil.rmtree(invenio / "assets", ignore_errors=True)
    shutil.rmtree(invenio / "static", ignore_errors=True)

    Path(invenio / "assets").mkdir(parents=True)
    Path(invenio / "static").mkdir(parents=True)

    check_call(
        [
            "pdm",
            "run",
            *(["--venv", pdm_name] if pdm_name else []),
            "invenio",
            "oarepo",
            "assets",
            "collect",
            f"{invenio}/watch.list.json",
        ],
        cwd=site_dir,
    )
    check_call(
        [
            "pdm",
            "invenio",
            *(["--venv", pdm_name] if pdm_name else []),
            "webpack",
            "clean",
            "create",
        ],
        cwd=site_dir,
    )
    check_call(
        [
            "pdm",
            "invenio",
            *(["--venv", pdm_name] if pdm_name else []),
            "webpack",
            "install",
        ],
        cwd=site_dir,
    )

    assets = site_dir / "assets"
    static = site_dir / "static"

    watched_paths = load_watched_paths(
        invenio / "watch.list.json", [f"{assets}=assets", f"{static}=static"]
    )

    copy_watched_paths(watched_paths, invenio)

    check_call(
        [
            "pdm",
            "run",
            *(["--venv", pdm_name] if pdm_name else []),
            "invenio",
            "webpack",
            "build",
        ],
        cwd=site_dir,
    )

    # do not allow Clean plugin to remove files
    webpack_config = (invenio / "assets" / "build" / "webpack.config.js").read_text()
    webpack_config = webpack_config.replace("dry: false", "dry: true")
    (invenio / "assets" / "build" / "webpack.config.js").write_text(webpack_config)
