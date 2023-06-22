import sys

import click as click

from oarepo_cli.site.site_support import SiteSupport
from oarepo_cli.utils import run_cmdline, with_config


@click.command(name="run", help="Run the server")
@click.option("-c", "--celery")
@click.argument("site", default=None, required=False)
@with_config()
def run_server(cfg=None, celery=False, site=None, **kwargs):
    site = SiteSupport(cfg, site)

    site.call_invenio(
        "run",
        "--cert",
        "docker/nginx/test.crt",
        "--key",
        "docker/nginx/test.key",
    )
