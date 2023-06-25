import shutil

from oarepo_cli.format.steps.base import BaseFormatStep
from oarepo_cli.site.site_support import SiteSupport
from oarepo_cli.utils import batched, run_cmdline


class FormatJavascriptStep(BaseFormatStep):
    def format_paths(self, model_paths, ui_paths, local_paths, site_paths):
        self.format_jsx(ui_paths + local_paths + site_paths, [])

    def format_jsx(self, dirs, exclude):
        site = SiteSupport(self.data)
        assets_dir = site.invenio_instance_path / "assets"
        if assets_dir.exists() and (assets_dir / "package.json").exists():
            # TODO: only when needed
            run_cmdline("npm", "install", cwd=assets_dir)
        else:
            return

        files = [
            f for f in self.find_files_with_extensions(dirs, "jsx", "tsx", "js", "ts")
        ]
        if not files:
            return
        # copy .eslintrc.json into invenio
        shutil.copy(
            site.site_dir / ".eslintrc.json",
            site.invenio_instance_path / "assets" / ".eslintrc.json",
        )
        for chunk in batched(files, 50):
            run_cmdline(
                site.invenio_instance_path
                / "assets"
                / "node_modules"
                / ".bin"
                / "eslint",
                "-c",
                ".eslintrc.json",
                "--fix",
                *chunk,
                cwd=assets_dir
            )
            run_cmdline(
                site.invenio_instance_path
                / "assets"
                / "node_modules"
                / ".bin"
                / "prettier",
                "--write",
                *chunk,
                cwd=assets_dir
            )
