from oarepo_cli.wizard import Wizard
from oarepo_cli.wizard.docker import DockerRunner

from ..site.site_support import SiteSupport
from .steps.format_javascript import FormatJavascriptStep
from .steps.format_jinja import FormatJinjaStep
from .steps.format_python import FormatPythonStep


class FormatWizard(Wizard):
    def __init__(self, runner: DockerRunner, site_support: SiteSupport):
        self.site_support = site_support
        steps = []
        steps.extend(
            runner.wrap_docker_steps(
                FormatPythonStep(),
                FormatJinjaStep(),
                FormatJavascriptStep(),
            )
        )
        super().__init__(*steps)
