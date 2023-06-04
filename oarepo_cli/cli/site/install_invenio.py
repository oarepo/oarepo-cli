import shutil

from oarepo_cli.cli.site.utils import SiteWizardStepMixin, get_site_local_packages
from oarepo_cli.wizard import WizardStep

from ...utils import run_cmdline


class InstallInvenioStep(SiteWizardStepMixin, WizardStep):
    def __init__(self, **kwargs):
        super().__init__(
            heading="""
Now I'll install invenio site.
            """,
            **kwargs,
        )

    def after_run(self):
        if not (self.site_dir / '.venv').exists():
            run_cmdline(
                "pdm",
                "venv",
                "create",
                "--with-pip",
                cwd=self.site_dir,
                environ={
                    'PDM_IGNORE_ACTIVE_VENV': '1'
                }
            )
        self.call_pip("install", "-U", "--no-input", "setuptools", "pip", "wheel")
        oarepo = (self.site_dir / 'requirements.txt').read_text().splitlines()[0]
        self.call_pip("install", "-U", "--no-input", oarepo)
        self.call_pip("install", "-U", "--no-input", "--no-deps", "-r",
                    str(self.site_dir / 'requirements.txt'))
        instance_dir = self.site_dir / '.venv' / 'var' / 'instance'
        if not instance_dir.exists():
            instance_dir.mkdir(parents=True)
        if not (instance_dir / 'invenio.cfg').exists():
            (instance_dir / 'invenio.cfg').symlink_to(self.site_dir / 'invenio.cfg')
        if not (instance_dir / 'variables').exists():
            (instance_dir / 'variables').symlink_to(self.site_dir / 'variables')

        # now install all the local packages without dependencies as these were already
        # collected in the requirements.txt

        # main site
        site_package_dir = self.site_dir.absolute() / 'site'
        for f in site_package_dir.glob('*.egg-info'):
            shutil.rmtree(f)
        self.call_pip("install", "-U", "--no-input", "--no-deps", "-e",
                    str(site_package_dir))

        # models and uis
        models, uis = get_site_local_packages(self.data)
        self.install_package(models, 'models')
        self.install_package(uis, 'ui')

    def install_package(self, packages, package_folder):
        for package in packages:
            package_dir = self.site_dir.absolute().parent.parent / package_folder / package
            for f in package_dir.glob('*.egg-info'):
                shutil.rmtree(f)
            self.call_pip("install", "-U", "--no-input", "--no-deps", "-e",
                        str(package_dir))

    def should_run(self):
        return True
