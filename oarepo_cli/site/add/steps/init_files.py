import subprocess

from minio import Minio

from oarepo_cli.site.mixins import SiteWizardStepMixin
from oarepo_cli.wizard import WizardStep


class InitFilesStep(SiteWizardStepMixin, WizardStep):
    def __init__(self, **kwargs):
        super().__init__(
            heading="""
        Now I will configure the default location for files storage in the minio s3 framework.
            """,
            **kwargs,
        )

    def after_run(self):
        host, port, access_key, secret_key = self.get_invenio_configuration(
            "INVENIO_S3_HOST",
            "INVENIO_S3_PORT",
            "INVENIO_S3_ACCESS_KEY",
            "INVENIO_S3_SECRET_KEY",
        )

        client = Minio(
            f"{host}:{port}",
            access_key=access_key,
            secret_key=secret_key,
            secure=False,
        )

        bucket_name = self.data["site_package"].replace(
            "_", ""
        )  # bucket names with underscores are not allowed
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)
        self.site_support.call_invenio(
            "files", "location", "default", f"s3://{bucket_name}", "--default"
        )
        self.check_file_location_initialized(raise_error=True)

    def check_file_location_initialized(self, raise_error=False):
        try:
            output = self.site_support.call_invenio(
                "files",
                "location",
                "list",
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
