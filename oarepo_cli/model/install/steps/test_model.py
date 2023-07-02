import shutil
import venv

from oarepo_cli.model.utils import ModelWizardStep
from oarepo_cli.utils import run_cmdline
from oarepo_cli.wizard import WizardStep


class RunTestsModelStep(ModelWizardStep, WizardStep):
    def after_run(self):
        if self.data["run_tests"] == "skip":
            return
        model_dir = self.model_dir
        venv_dir = model_dir / ".venv-test"
        if venv_dir.exists():
            shutil.rmtree(venv_dir)

        venv.main([str(venv_dir)])
        pip_binary = venv_dir / "bin" / "pip"
        pytest_binary = venv_dir / "bin" / "pytest"

        run_cmdline(
            pip_binary, "install", "-U", "--no-input", "setuptools", "pip", "wheel"
        )
        run_cmdline(
            pip_binary, "install", "--no-input", "-e", ".[tests]", cwd=model_dir
        )

        run_cmdline(
            pytest_binary,
            "tests",
            cwd=model_dir,
            environ={
                "OPENSEARCH_HOST": self.data.get(
                    "config.TEST_OPENSEARCH_HOST", "localhost"
                ),
                "OPENSEARCH_PORT": self.data.get("config.TEST_OPENSEARCH_PORT", "9400"),
            },
        )

    def should_run(self):
        return True
