import json
import os
import re
import shutil
import tempfile
from pathlib import Path

from oarepo_cli.config import MonorepoConfig
from oarepo_cli.utils import run_cmdline


class SiteSupport:
    def __init__(self, config: MonorepoConfig, site_section=None):
        self.config = config
        if config.section_path[0] == "sites":
            self.site = config
            self.site_name = config.section_path[-1]
            return
        elif not site_section:
            sites = config.whole_data.get("sites", {})
            if len(sites) == 1:
                site_section = next(iter(sites.keys()))
            else:
                raise RuntimeError("no or more sites, please specify --site or similar")
        self.site = config.whole_data.get("sites", {})[site_section]
        self.site_name = site_section

    @property
    def site_dir(self):
        return Path(self.config.project_dir) / self.site["site_dir"]

    @property
    def python(self):
        if self.config.running_in_docker:
            return "python3"
        return self.config.whole_data["config"]["python"]

    def call_pdm(self, *args, **kwargs):
        pdm_binary = self.site.get("pdm_binary", "pdm")
        return run_cmdline(
            pdm_binary,
            *args,
            cwd=self.site_dir,
            environ={"PDM_IGNORE_ACTIVE_VENV": "1"},
            **kwargs,
        )

    @property
    def virtualenv(self):
        return Path(os.environ.get("INVENIO_VENV", self.site_dir / ".venv"))

    @property
    def invenio_instance_path(self):
        return Path(
            os.environ.get(
                "INVENIO_INSTANCE_PATH", self.virtualenv / "var" / "instance"
            )
        )

    def call_pip(self, *args, **kwargs):
        return run_cmdline(
            self.virtualenv / "bin" / "pip",
            *args,
            **{
                "cwd": self.site_dir,
                "raise_exception": True,
                **kwargs,
            },
        )

    def call_invenio(self, *args, **kwargs):
        return run_cmdline(
            self.virtualenv / "bin" / "invenio",
            *args,
            **{
                "cwd": self.site_dir,
                "raise_exception": True,
                **kwargs,
            },
        )

    def get_site_local_packages(self):
        models = [
            model_name
            for model_name, model_section in self.config.whole_data.get(
                "models", {}
            ).items()
            if self.config.section in model_section.get("sites")
        ]
        uis = [
            ui_name
            for ui_name, ui_section in self.config.whole_data.get("ui", {}).items()
            if self.config.section in ui_section.get("sites")
        ]
        local_packages = [
            local_name
            for local_name, local_section in self.config.whole_data.get(
                "local", {}
            ).items()
            if self.config.section in local_section.get("sites")
        ]
        return models, uis, local_packages

    def create_virtualenv(self, clean=False):
        if self.virtualenv.exists():
            # check if the virtualenv is usable - try to run python
            try:
                run_cmdline(
                    self.virtualenv / "bin" / "python",
                    "--version",
                    raise_exception=True,
                )
                run_cmdline(
                    self.virtualenv / "bin" / "pip", "list", raise_exception=True
                )
            except:
                clean = True
            if clean:
                shutil.rmtree(self.virtualenv)
            else:
                # nothing to create, it exists
                return

        cmdline = [
            self.python,
            "-m",
            "venv",
        ]
        if self.config.running_in_docker:
            # alpine image has a pre-installed deps, keep them here
            cmdline.append('--system-site-packages')

        run_cmdline(
            *cmdline, str(self.virtualenv), cwd=self.site_dir, raise_exception=True
        )
        self.call_pip(
            "install",
            "-U",
            "--no-input",
            "setuptools",
            "pip",
            "wheel",
        )

    def _get_oarepo_dependencies(self, oarepo):
        self.call_pip("download", "--no-deps", "--no-binary=:all:", oarepo, cwd="/tmp")
        tar_name = "/tmp/" + oarepo.replace("==", "-") + ".tar.gz"
        # extract the tar
        with tempfile.TemporaryDirectory() as temp_dir:
            import tarfile

            tf = tarfile.open(tar_name, mode="r:gz")
            tf.extractall(path=temp_dir)
            content_dir = temp_dir + "/" + oarepo.replace("==", "-")
            run_cmdline(
                self.virtualenv / "bin" / "python",
                "setup.py",
                "egg_info",
                cwd=content_dir,
            )
            requires = (
                Path(content_dir) / "oarepo.egg-info" / "requires.txt"
            ).read_text()
            requires = requires.split("\n\n")[0]

            # install some core packages if they are not already pre-installed
            # TODO: modify oarepo not to exclude packages and do difference to
            # actual venv in the installation steps

            extra_packages = [
                "libcst",
                "cchardet",
                "uwsgi",
                "ruamel.yaml.clib",
                "cairocffi",
                "cffi",
                "packaging",
                "pyparsing"
            ]
            requires = requires.split('\n')
            found_extras = []
            for r in requires:
                r = re.split('[=><]', r, maxsplit=1)
                if r[0] in extra_packages:
                    found_extras.append(r[0])
            requires.extend(set(extra_packages) - set(found_extras))

            return requires

    def _install_oarepo_dependencies(self, oarepo):
        requires = self._get_oarepo_dependencies(oarepo)
        # load already installed packages
        installed_json = json.loads(self.call_pip(
            "list",
            "--format", "json",
            grab_stdout=True
        ))
        installed_packages = set(x['name'] for x in installed_json)
        requirements_to_install = []
        for r in requires:
            package_name = re.split('[=><]', r, maxsplit=1)[0]
            if package_name not in installed_packages:
                requirements_to_install.append(r)

        with tempfile.NamedTemporaryFile(
            mode="wt", suffix="-requirements.txt"
        ) as temp_file:
            temp_file.write('\n'.join(requirements_to_install))
            temp_file.flush()
            self.call_pip("install", "--no-deps", "-r", temp_file.name)

        # hack: add an empty version of uritemplate.py,
        # needs to be removed when invenio-oauthclient gets updated
        self.call_pip("install", "--force-reinstall", str(
            Path(__file__).parent / 'uritemplate.py-1.999.999.tar.gz')
        )
        # this is needed to fix installation problems on osx (not all requirements
        # seems to be built inside oarepo package for darwin architecture)
        self.call_pip("install", "--force-reinstall", 'ipython')

    def install_site(self):
        oarepo = (self.site_dir / "requirements.txt").read_text().splitlines()[0]

        self._install_oarepo_dependencies(oarepo)
        self.call_pip(
            "install",
            "-U",
            "--no-input",
            "--no-deps",
            "-r",
            str(self.site_dir / "requirements.txt"),
        )
        instance_dir = self.invenio_instance_path
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
        self.call_pip(
            "install", "-U", "--no-input", "--no-deps", "-e", str(site_package_dir)
        )

        # models and uis
        models, uis, local_packages = self.get_site_local_packages()
        self._install_package(models, "models")
        self._install_package(uis, "ui")
        self._install_package(local_packages, "local")

    def _install_package(self, packages, package_folder):
        for package in packages:
            package_dir = (
                self.site_dir.absolute().parent.parent / package_folder / package
            )
            if not package_dir.exists():
                continue
            for f in package_dir.glob("*.egg-info"):
                shutil.rmtree(f)
            self.call_pip(
                "install", "-U", "--no-input", "--no-deps", "-e", str(package_dir)
            )
