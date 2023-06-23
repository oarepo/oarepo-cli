import json
import shutil
import tempfile
from pathlib import Path

from oarepo_cli.site.mixins import SiteWizardStepMixin
from oarepo_cli.utils import run_cmdline
from oarepo_cli.wizard import WizardStep


class InstallInvenioStep(SiteWizardStepMixin, WizardStep):
    def __init__(self, clean=False, **kwargs):
        super().__init__(
            heading="""
Now I'll install invenio site.
            """,
            **kwargs,
        )
        self.clean = clean

    def after_run(self):
        # if running in docker, the virtualenv is already there
        if not self.data.running_in_docker:
            if self.clean and self.site_support.virtualenv.exists():
                shutil.rmtree(self.site_support.virtualenv)

            cmdline = [
                self.site_support.python,
                "-m",
                "venv",
            ]

            run_cmdline(
                *cmdline,
                str(self.site_support.virtualenv),
                cwd=self.site_dir,
            )
            self.site_support.call_pip(
                "install", "-U", "--no-input", "setuptools", "pip", "wheel"
            )
        elif self.clean:
            listing = json.loads(self.site_support.call_pip(
                "list", "--format", "json", grab_stdout=True
            ))
            packages = [pkg['name'] for pkg in listing if pkg['name'] not in ('setuptools', 'pip', 'wheel')]
            self.site_support.call_pip(
                "uninstall", '-y', *packages
            )
            self.site_support.call_pip(
                "install", "-U", "--no-input", "setuptools", "pip", "wheel"
            )

        oarepo = (self.site_dir / "requirements.txt").read_text().splitlines()[0]
        self.install_oarepo_dependencies(oarepo)
        self.site_support.call_pip(
            "install",
            "-U",
            "--no-input",
            "--no-deps",
            "-r",
            str(self.site_dir / "requirements.txt"),
        )
        instance_dir = self.site_support.invenio_instance_path
        if not instance_dir.exists():
            instance_dir.mkdir(parents=True)
        if not (instance_dir / "invenio.cfg").exists():
            (instance_dir / "invenio.cfg").symlink_to(self.site_dir / "invenio.cfg")
        if not (instance_dir / "variables").exists():
            (instance_dir / "variables").symlink_to(self.site_dir / "variables")

        # now install all the local packages without dependencies as these were already
        # collected in the requirements.txt

        # main site
        site_package_dir = self.site_dir.absolute() / "site"
        for f in site_package_dir.glob("*.egg-info"):
            shutil.rmtree(f)
        self.site_support.call_pip(
            "install", "-U", "--no-input", "--no-deps", "-e", str(site_package_dir)
        )

        # models and uis
        models, uis, local_packages = self.site_support.get_site_local_packages()
        self.install_package(models, "models")
        self.install_package(uis, "ui")
        self.install_package(local_packages, "local")

    def get_oarepo_dependencies(self, oarepo):
        self.site_support.call_pip(
            "download", "--no-deps", "--no-binary=:all:", oarepo, cwd="/tmp"
        )
        tar_name = "/tmp/" + oarepo.replace("==", "-") + ".tar.gz"
        # extract the tar
        with tempfile.TemporaryDirectory() as temp_dir:
            import tarfile

            tf = tarfile.open(tar_name, mode="r:gz")
            tf.extractall(path=temp_dir)
            content_dir = temp_dir + "/" + oarepo.replace("==", "-")
            run_cmdline(
                self.site_support.python, "setup.py", "egg_info", cwd=content_dir
            )
            requires = (
                Path(content_dir) / "oarepo.egg-info" / "requires.txt"
            ).read_text()
            requires = requires.split("\n\n")[0]
            return requires

    def install_oarepo_dependencies(self, oarepo):
        requires = self.get_oarepo_dependencies(oarepo)
        with tempfile.NamedTemporaryFile(
            mode="wt", suffix="-requirements.txt"
        ) as temp_file:
            temp_file.write(requires)
            temp_file.flush()
            self.site_support.call_pip("install", "--no-deps", "-r", temp_file.name)

    def install_package(self, packages, package_folder):
        for package in packages:
            package_dir = (
                self.site_dir.absolute().parent.parent / package_folder / package
            )
            if not package_dir.exists():
                continue
            for f in package_dir.glob("*.egg-info"):
                shutil.rmtree(f)
            self.site_support.call_pip(
                "install", "-U", "--no-input", "--no-deps", "-e", str(package_dir)
            )

    def should_run(self):
        return True
