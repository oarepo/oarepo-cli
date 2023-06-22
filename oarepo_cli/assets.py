import shutil
from pathlib import Path

from oarepo_cli.config import MonorepoConfig
from oarepo_cli.site.site_support import SiteSupport
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


def build_assets(*, cfg: MonorepoConfig, site_name, **kwargs):
    site = SiteSupport(cfg, site_name)
    invenio_instance_path = site.invenio_instance_path

    shutil.rmtree(invenio_instance_path / "assets", ignore_errors=True)
    shutil.rmtree(invenio_instance_path / "static", ignore_errors=True)

    Path(invenio_instance_path / "assets").mkdir(parents=True)
    Path(invenio_instance_path / "static").mkdir(parents=True)

    site.call_invenio(
        "oarepo",
        "assets",
        "collect",
        f"{invenio_instance_path}/watch.list.json",
    )
    site.call_invenio(
        "webpack",
        "clean",
        "create",
    )
    site.call_invenio(
        "webpack",
        "install",
    )

    assets = invenio_instance_path / "assets"
    static = invenio_instance_path / "static"

    watched_paths = load_watched_paths(
        invenio_instance_path / "watch.list.json",
        [f"{assets}=assets", f"{static}=static"],
    )

    copy_watched_paths(watched_paths, invenio_instance_path)

    site.call_invenio(
        "webpack",
        "build",
    )

    # do not allow Clean plugin to remove files
    webpack_config = (
        invenio_instance_path / "assets" / "build" / "webpack.config.js"
    ).read_text()
    webpack_config = webpack_config.replace("dry: false", "dry: true")
    (invenio_instance_path / "assets" / "build" / "webpack.config.js").write_text(
        webpack_config
    )
