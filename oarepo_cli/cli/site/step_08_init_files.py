import subprocess

from oarepo_cli.cli.site.utils import SiteWizardStepMixin
from oarepo_cli.ui.wizard import WizardStep

from ...utils import run_cmdline


class InitFilesStep(SiteWizardStepMixin, WizardStep):
    def __init__(self, **kwargs):
        super().__init__(
            heading="""
        Now I will configure the default location for files storage in the minio s3 framework.
            """,
            **kwargs,
        )

    def after_run(self):
        from minio import Minio

        client = Minio(
            "localhost:9000",
            access_key="CHANGE_ME",
            secret_key="CHANGE_ME",
            secure=False,
        )
        bucket_name = self.data["site_package"].replace(
            "_", ""
        )  # bucket names with underscores are not allowed
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)
        run_cmdline(
            "pipenv",
            "run",
            "invenio",
            "files",
            "location",
            "default",
            f"s3://{bucket_name}",
            "--default",
            cwd=self.site_dir,
            environ={"PIPENV_IGNORE_VIRTUALENVS": "1"},
        )
        self.check_file_location_initialized(raise_error=True)

    def check_file_location_initialized(self, raise_error=False):
        try:
            output = run_cmdline(
                "pipenv",
                "run",
                "invenio",
                "files",
                "location",
                "list",
                cwd=self.site_dir,
                environ={"PIPENV_IGNORE_VIRTUALENVS": "1"},
                grab_stdout=True,
                raise_exception=True,
            )
            print(f"initialization check:\n{output}\n")
        except subprocess.CalledProcessError:
            raise Exception("Checking if file location exists failed.")
        if output:
            return True
        else:
            if raise_error:
                raise Exception(
                    "No file location exists. This probably means that the wizard was unable to create one."
                )
            return False

    def should_run(self):
        return not self.check_file_location_initialized(raise_error=False)
