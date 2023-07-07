import json
import re
from pathlib import Path

from oarepo_cli.utils import copy_tree

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


def register_less_components(site, invenio_instance_path):
    site.call_invenio(
        "oarepo",
        "assets",
        "less-components",
        f"{invenio_instance_path}/less-components.json",
    )
    data = json.loads(Path(f"{invenio_instance_path}/less-components.json").read_text())
    components = list(set(data["components"]))
    theme_config_file = site.site_dir / "assets" / "less" / "theme.config"
    theme_data = theme_config_file.read_text()
    for c in components:
        match = re.search("^@" + c, theme_data, re.MULTILINE)
        if not match:
            match = theme_data.index("/* @my_custom_component : 'default'; */")
            theme_data = (
                theme_data[:match] + f"\n@{c}: 'default';\n" + theme_data[match:]
            )
    theme_config_file.write_text(theme_data)


def load_watched_paths(paths_json, extra_paths):
    watched_paths = {}
    with open(paths_json) as f:
        for target, paths in json.load(f).items():
            if target.startswith("@"):
                continue
            for pth in paths:
                watched_paths[pth] = target
    for e in extra_paths:
        source, target = e.split("=", maxsplit=1)
        watched_paths[source] = target
    return watched_paths


def copy_watched_paths(watched_paths, destination):
    destination.mkdir(parents=True, exist_ok=True)
    for source, target in watched_paths.items():
        copy_tree(Path(source).absolute(), destination.absolute() / target)
