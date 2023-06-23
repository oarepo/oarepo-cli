import os.path
from collections import defaultdict
from pathlib import Path

from oarepo_cli.format.steps.base import BaseFormatStep
from oarepo_cli.site.site_support import SiteSupport
from oarepo_cli.utils import batched, run_cmdline
from oarepo_cli.wizard import WizardStep


class FormatJinjaStep(BaseFormatStep):

    def format_paths(self, model_paths, ui_paths, local_paths, site_paths):
        self.format_jinja(ui_paths + local_paths, exclude=[])

    def format_jinja(self, dirs, exclude):
        # look for 'templates' folder inside the paths
        from djlint import Config, process
        for f in self.find_files_with_extensions(dirs, "html"):
            if not "templates" in f.parts:
                continue
            config = Config(src=f, profile="jinja", reformat=True)
            process(config, f)

