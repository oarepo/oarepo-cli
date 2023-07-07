from __future__ import annotations

import re

from oarepo_cli.site.mixins import SiteWizardStepMixin
from oarepo_cli.utils import run_cmdline
from oarepo_cli.wizard import WizardStep


class CheckRequirementsStep(SiteWizardStepMixin, WizardStep):
    def __init__(self, **kwargs):
        super().__init__(
            heading="""
I will check the requirements for Invenio site installation.
            """,
            **kwargs,
        )

    def after_run(self):
        # no check for python performed
        self._check_pdm_callable()
        self._check_docker_callable()
        self._check_docker_compose_version(1, 17)
        self._check_node_version(14, 16)
        self._check_npm_version(6, 7, 8)
        self._check_imagemagick_callable()
        with open(self.site_dir / ".check.ok", "w") as f:
            f.write("invenio check ok")

    def should_run(self):
        return not (self.site_dir / ".check.ok").exists()

    def _check_docker_callable(self):
        if self.data.running_in_docker:
            return
        run_cmdline("docker", "ps", grab_stdout=True)

    def _check_pdm_callable(self):
        run_cmdline(
            "pdm",
            "--version",
            environ={"PDM_IGNORE_ACTIVE_VENV": "1"},
            grab_stdout=True,
        )

    def _check_imagemagick_callable(self):
        run_cmdline("convert", "--version", grab_stdout=True)

    def check_version(self, *args, expected_major, expected_minor=None, strict=False):
        result = run_cmdline(*args, grab_stdout=True)
        self.vprint(f"Version string is: {result}")
        version_result = re.search(r".*?([0-9]+)\.([0-9]+)\.([0-9]+)", result)
        major = int(version_result.groups()[0])
        minor = int(version_result.groups()[1])
        if strict:
            if isinstance(expected_major, (list, tuple)):
                assert (
                    major in expected_major
                ), f"Expected major version to be one of {expected_major}, found {major}"
            else:
                assert (
                    major == expected_major
                ), f"Expected major version to be one {expected_major}, found {major}"
                if expected_minor:
                    assert minor == expected_minor
        elif not (
            major > expected_major
            or (major == expected_major and minor >= expected_minor)
        ):
            raise Exception("Expected docker compose version ")

    def _check_docker_compose_version(self, expected_major, expected_minor):
        if self.data.running_in_docker:
            return
        self.check_version(
            "docker",
            "compose",
            "version",
            expected_major=expected_major,
            expected_minor=expected_minor,
        )

    def _check_node_version(self, *supported_versions):
        self.check_version(
            "node", "--version", expected_major=supported_versions, strict=True
        )

    def _check_npm_version(self, *supported_versions):
        self.check_version(
            "npm", "--version", expected_major=supported_versions, strict=True
        )
