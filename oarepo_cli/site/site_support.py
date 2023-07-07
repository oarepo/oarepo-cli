import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import requirements
import tomli_w
from dotenv import dotenv_values
from minio import Minio

from oarepo_cli.config import MonorepoConfig
from oarepo_cli.package_versions import OAREPO_VERSION, PYTHON_VERSION
from oarepo_cli.utils import run_cmdline


class SiteSupport:
    def __init__(self, config: MonorepoConfig, site_section=None):
        if config.section_path[0] == "sites":
            self.site = config
            self.site_name = config.section_path[-1]
            self.config = config
            return
        elif not site_section:
            sites = config.whole_data.get("sites", {})
            if len(sites) == 1:
                site_section = next(iter(sites.keys()))
            else:
                raise RuntimeError("no or more sites, please specify --site or similar")

        self.site = config.whole_data.get("sites", {})[site_section]
        self.site_name = site_section
        self.config = config.clone(["sites", self.site_name])

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
            if self.config.section in model_section.get("sites", [])
        ]
        uis = [
            ui_name
            for ui_name, ui_section in self.config.whole_data.get("ui", {}).items()
            if self.config.section in ui_section.get("sites", [])
        ]
        local_packages = [
            local_name
            for local_name, local_section in self.config.whole_data.get(
                "local", {}
            ).items()
            if self.config.section in local_section.get("sites", [])
        ]
        return models, uis, local_packages

    def venv_ok(self):
        if self.virtualenv.exists():
            # check if the virtualenv is usable - try to run python
            try:
                run_cmdline(
                    self.virtualenv / "bin" / "python",
                    "--version",
                    raise_exception=True,
                )
                run_cmdline(
                    self.virtualenv / "bin" / "pip",
                    "list",
                    raise_exception=True,
                    grab_stdout=True,
                )
                return True
            except:
                pass
        return False

    def check_and_create_virtualenv(self, clean=False):
        if not self.venv_ok():
            clean = True

        if clean and self.virtualenv.exists():
            shutil.rmtree(self.virtualenv)

        cmdline = [
            self.python,
            "-m",
            "venv",
        ]
        if self.config.running_in_docker:
            # alpine image has a pre-installed deps, keep them here
            cmdline.append("--system-site-packages")

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
                "pyparsing",
            ]
            requires = requires.split("\n")
            found_extras = []
            for r in requires:
                r = re.split("[=><]", r, maxsplit=1)
                if r[0] in extra_packages:
                    found_extras.append(r[0])
            requires.extend(set(extra_packages) - set(found_extras))

            return requires

    def _install_oarepo_dependencies(self, oarepo):
        print("Install oarepo dependencies called")
        requires = self._get_oarepo_dependencies(oarepo)
        # load already installed packages
        installed_json = json.loads(
            self.call_pip("list", "--format", "json", grab_stdout=True)
        )
        installed_packages = set(x["name"].lower() for x in installed_json)
        requirements_to_install = []
        for r in requires:
            package_name = re.split("[=><]", r, maxsplit=1)[0]
            if package_name.lower() not in installed_packages:
                requirements_to_install.append(r.lower())
        print("Installed packages", installed_packages)
        print("Requirements to install", requirements_to_install)

        # this is needed to fix installation problems on osx (not all requirements
        # seems to be built inside oarepo package for darwin architecture)
        self.call_pip("install", "--force-reinstall", "ipython")

        # and call the following with force reinstall as ipython might override something
        with tempfile.NamedTemporaryFile(
            mode="wt", suffix="-requirements.txt"
        ) as temp_file:
            temp_file.write("\n".join(requirements_to_install))
            temp_file.flush()
            self.call_pip(
                "install", "--no-deps", "--force-reinstall", "-r", temp_file.name
            )

        # hack: add an empty version of uritemplate.py,
        # needs to be removed when invenio-oauthclient gets updated
        self.call_pip(
            "install",
            "--force-reinstall",
            str(Path(__file__).parent / "uritemplate.py-1.999.999.tar.gz"),
        )

    def site_ok(self):
        try:
            self.call_invenio("--help", raise_exception=True, grab_stdout=True)
        except:
            return False

        models, uis, local_packages = self.get_site_local_packages()
        invenio_ts = (self.virtualenv / "bin" / "invenio").lstat().st_mtime
        print(f"Invenio has timestamp {invenio_ts}")
        if self.packages_newer(models, "models", invenio_ts):
            return False
        if self.packages_newer(uis, "ui", invenio_ts):
            return False
        if self.packages_newer(local_packages, "local", invenio_ts):
            return False
        return True

    def packages_newer(self, packages, package_folder, timestamp):
        for package in packages:
            package_dir = (
                self.site_dir.absolute().parent.parent / package_folder / package
            )
            if not package_dir.exists():
                continue
            for fn in package_dir.glob("*"):
                if 'egg' in fn.name:
                    continue
                if fn.lstat().st_mtime > timestamp:
                    print(
                        f"Package {fn} with timestamp {fn.lstat().st_mtime} is newer than {timestamp}"
                    )
                    return True
        return False

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

        # touch invenio to mark the installation timestamp
        (self.virtualenv / "bin" / "invenio").touch()

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

    def build_ui(self, production=False):
        from oarepo_cli.site.assets import (
            copy_watched_paths,
            load_watched_paths,
            register_less_components,
        )

        invenio_instance_path = self.invenio_instance_path.resolve()

        shutil.rmtree(invenio_instance_path / "assets", ignore_errors=True)
        shutil.rmtree(invenio_instance_path / "static", ignore_errors=True)

        Path(invenio_instance_path / "assets").mkdir(parents=True)
        Path(invenio_instance_path / "static").mkdir(parents=True)

        register_less_components(self, invenio_instance_path)

        self.call_invenio(
            "oarepo",
            "assets",
            "collect",
            f"{invenio_instance_path}/watch.list.json",
        )
        self.call_invenio(
            "webpack",
            "clean",
            "create",
        )
        self.call_invenio(
            "webpack",
            "install",
        )

        assets = (self.site_dir / "assets").resolve()
        static = (self.site_dir / "static").resolve()

        watched_paths = load_watched_paths(
            invenio_instance_path / "watch.list.json",
            [f"{assets}=assets", f"{static}=static"],
        )

        copy_watched_paths(watched_paths, invenio_instance_path)

        self.call_invenio("webpack", "build", *(["--production"] if production else []))

        # do not allow Clean plugin to remove files
        webpack_config = (
            invenio_instance_path / "assets" / "build" / "webpack.config.js"
        ).read_text()
        webpack_config = webpack_config.replace("dry: false", "dry: true")
        (invenio_instance_path / "assets" / "build" / "webpack.config.js").write_text(
            webpack_config
        )

    def ui_ok(self):
        # check that there is a manifest.json there
        manifest = self.invenio_instance_path / "static" / "dist" / "manifest.json"
        if not manifest.exists():
            return False
        try:
            json_data = json.loads(manifest.read_text())
            if json_data.get("status") != "done":
                return False
        except:
            return False
        return True

    def rebuild_site(self, clean=False, build_ui=False):
        self.check_and_create_virtualenv(clean=clean)
        self.build_dependencies()
        self.install_site()
        if build_ui:
            self.build_ui()

    def build_dependencies(self):
        # create pyproject.toml file
        models, uis, local_packages = self.get_site_local_packages()
        extras = [
            *[
                f"{model} @ file:///${{PROJECT_ROOT}}/../../models/{model}"
                for model in models
                if (self.site_dir.parent.parent / "models" / model).exists()
            ],
            *[
                f"{ui} @ file:///${{PROJECT_ROOT}}/../../ui/{ui}"
                for ui in uis
                if (self.site_dir.parent.parent / "ui" / ui).exists()
            ],
            *[
                f"{local} @ file:///${{PROJECT_ROOT}}/../../local/{local}"
                for local in local_packages
                if (self.site_dir.parent.parent / "local" / local).exists()
            ],
            "site @ file:///${PROJECT_ROOT}/site",
        ]
        # generate requirements just for oarepo package
        oarepo_requirements = self.generate_requirements([])
        oarepo_requirements = list(requirements.parse(oarepo_requirements))

        # get the current version of oarepo
        oarepo_requirement = [x for x in oarepo_requirements if x.name == "oarepo"][0]

        # generate requirements for the local packages as well
        all_requirements = self.generate_requirements(extras)
        all_requirements = list(requirements.parse(all_requirements))

        # now make the difference of those two (we do not want to have oarepo dependencies in the result)
        # as oarepo will be installed to virtualenv separately (to handle system packages)
        oarepo_requirements_names = {x.name for x in oarepo_requirements}
        non_oarepo_requirements = [
            x for x in all_requirements if x.name not in oarepo_requirements_names
        ]

        # remove local packages
        non_oarepo_requirements = [
            x for x in non_oarepo_requirements if "file://" not in x.line
        ]

        # and generate final requirements
        resolved_requirements = "\n".join(
            [oarepo_requirement.line, *[x.line for x in non_oarepo_requirements]]
        )
        (self.site_dir / "requirements.txt").write_text(resolved_requirements)

    def generate_requirements(self, extras):
        pdm_file = {
            "project": {
                "name": f"{self.config.section}-repository",
                "version": "1.0.0",
                "description": "",
                "packages": [],
                "authors": [
                    {
                        "name": self.config["author_name"],
                        "email": self.config["author_email"],
                    },
                ],
                "dependencies": [OAREPO_VERSION, *extras],
                "requires-python": PYTHON_VERSION,
            }
        }
        with open(self.site_dir / "pyproject.toml", "wb") as f:
            tomli_w.dump(pdm_file, f)

        self.call_pdm(
            "lock",
        )
        return self.call_pdm(
            "export", "-f", "requirements", "--without-hashes", grab_stdout=True
        )

    def init_files(self):
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

        bucket_name = self.config["site_package"].replace(
            "_", ""
        )  # bucket names with underscores are not allowed
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)
        self.call_invenio(
            "files", "location", "default", f"s3://{bucket_name}", "--default"
        )
        self.check_file_location_initialized(raise_error=True)

    def check_file_location_initialized(self, raise_error=False):
        try:
            output = self.call_invenio(
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

    def get_invenio_configuration(self, *keys):
        values = dotenv_values(self.site_dir / "variables")
        values.update({k: v for k, v in os.environ.items() if k.startswith("INVENIO_")})

        def convert(x):
            try:
                if x == "False":
                    return False
                if x == "True":
                    return True
                return json.loads(x)
            except:
                return x

        try:
            return [convert(values[x]) for x in keys]
        except KeyError as e:
            raise KeyError(
                f"Configuration key not found in defaults: {values.keys()}: {e}"
            )
