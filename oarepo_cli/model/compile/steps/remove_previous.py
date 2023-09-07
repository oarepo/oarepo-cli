from pathlib import Path

from colorama import Fore, Style

from oarepo_cli.model.utils import ModelWizardStep
from oarepo_cli.wizard import RadioStep


class RemovePreviousModelStep(ModelWizardStep):
    def __init__(self):
        super().__init__(
            RadioStep(
                "merge_changes",
                options={
                    "merge": "Merge changes into the previously generated files",
                    "overwrite": "Remove previously generated files and start from scratch",
                },
                default="merge",
                heading=f"""
It seems that the model has been already generated. 

Should I try to {Fore.GREEN}merge{Fore.BLUE} the changes with the existing sources 
or {Fore.RED}remove{Fore.BLUE} the previously generated sources and generate from scratch?

{Fore.YELLOW}Please make sure that you have your existing sources safely committed into git repository
so that you might recover them if the compilation process fails.{Style.RESET_ALL}
""",
            )
        )

    def should_run(self):
        return (self.model_dir / "setup.cfg").exists()

    def after_run(self):
        if self.data.get("merge_changes") == "overwrite":

            def _rm(x: Path, *, exceptions: set = None, stack=None):
                # print("Removing", x, stack, exceptions)
                if not stack:
                    stack = []
                if x.exists():
                    if x.is_dir():
                        for child in x.iterdir():
                            stack.append(child.name)
                            _rm(child, exceptions=exceptions, stack=stack)
                            stack.pop()
                        if not list(x.iterdir()):
                            if not exceptions or not exceptions.intersection(stack):
                                x.rmdir()
                    else:
                        if not exceptions or not exceptions.intersection(stack):
                            x.unlink()

            _rm(self.model_package_dir, exceptions={"alembic"})
            _rm(self.model_dir / "tests")
            _rm(self.model_dir / "setup.cfg")
            _rm(self.model_dir / "data")
