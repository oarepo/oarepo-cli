import json
import os
import re

from colorama import Fore, Style

from oarepo_cli.model.utils import ModelWizardStep


class CreateAlembicModelStep(ModelWizardStep):
    heading = f"""
    I will create/update the alembic migration steps so that you might later modify 
    the model and perform automatic database migrations. This command will write
    alembic steps (if the database layer has been modified) to the models' alembic directory.
                """
    pause = True

    def after_run(self):
        model_file = self.model_package_dir / "models" / "records.json"

        with open(model_file) as f:
            model_data = json.load(f)

        alembic_path = self.model_dir / model_data["model"]["record-metadata"][
            "alembic"
        ].replace(".", "/")
        branch = model_data["model"]["record-metadata"]["alias"]
        self.setup_alembic(branch, alembic_path)

    def get_alembic_path(self, model_dir):
        md = model_dir
        while md != self.model_dir:
            ap = md / "alembic"
            if ap.exists():
                return ap
            md = md.parent

    def setup_alembic(self, branch, alembic_path):
        filecount = len(
            [
                x
                for x in alembic_path.iterdir()
                if x.is_file() and x.name.endswith(".py")
            ]
        )
        revision_id_prefix = branch

        def rewrite_revision_file(file_suffix, new_id_number):
            files = list(alembic_path.iterdir())
            suffixed_files = [
                file_name for file_name in files if file_suffix in str(file_name)
            ]

            if not suffixed_files:
                return

            target_file = str(suffixed_files[0])
            id_start_index = target_file.rfind("/") + 1
            id_end_index = target_file.find(file_suffix)
            old_id = target_file[id_start_index:id_end_index]
            new_id = f"{revision_id_prefix}_{new_id_number}"
            with open(target_file, "r") as f:
                file_text = f.read()
                file_text = file_text.replace(
                    f"revision = '{old_id}'", f"revision = '{new_id}'"
                )
            with open(target_file.replace(old_id, new_id), "w") as f:
                f.write(file_text)
            os.remove(target_file)

        if filecount < 2:
            # alembic has not been initialized yet ...
            self.site_support.call_invenio(
                "alembic", "upgrade", "heads", cwd=self.site_dir
            )
            # create model branch
            self.site_support.call_invenio(
                "alembic",
                "revision",
                f"Create {branch} branch for {self.data['model_package']}.",
                "-b",
                branch,
                "-p",
                "dbdbc1b19cf2",
                "--empty",
                cwd=self.site_dir,
            )

            rewrite_revision_file("_create_", "1")

            self.fix_sqlalchemy_utils(alembic_path)
            self.site_support.call_invenio(
                "alembic", "upgrade", "heads", cwd=self.site_dir
            )
            self.site_support.call_invenio(
                "alembic",
                "revision",
                "Initial revision.",
                "-b",
                branch,
                cwd=self.site_dir,
            )

            rewrite_revision_file(
                "_initial_revision", "2"
            )  # the link to down-revision is created correctly after alembic upgrade heads on the corrected file, explicit rewrite of down-revision is not needed

            self.fix_sqlalchemy_utils(alembic_path)
            self.site_support.call_invenio(
                "alembic", "upgrade", "heads", cwd=self.site_dir
            )
        else:
            # alembic has been initialized, update heads and generate
            files = [file_path.name for file_path in alembic_path.iterdir()]

            file_numbers = []
            for file in files:
                file_number_regex = re.findall(f"(?<={revision_id_prefix}_)\d+", file)
                if file_number_regex:
                    file_numbers.append(int(file_number_regex[0]))
            new_file_number = max(file_numbers) + 1

            self.site_support.call_invenio("alembic", "upgrade", "heads")
            self.site_support.call_invenio(
                "alembic",
                "revision",
                "nrp install revision.",
                "-b",
                branch,
            )

            rewrite_revision_file("_nrp_cli_install", new_file_number)

            self.fix_sqlalchemy_utils(alembic_path)
            self.site_support.call_invenio("alembic", "upgrade", "heads")

    def fix_sqlalchemy_utils(self, alembic_path):
        for fn in alembic_path.iterdir():
            if not fn.name.endswith(".py"):
                continue
            data = fn.read_text()

            empty_migration = '''
def upgrade():
    """Upgrade database."""
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###'''

            if empty_migration in data:
                print(
                    f"{Fore.YELLOW}Found empty migration in file {fn}, deleting it{Style.RESET_ALL}"
                )
                fn.unlink()
                continue

            modified = False
            if "import sqlalchemy_utils" not in data:
                data = "import sqlalchemy_utils\n" + data
                modified = True
            if "import sqlalchemy_utils.types" not in data:
                data = "import sqlalchemy_utils.types\n" + data
                modified = True
            if modified:
                fn.write_text(data)

    def should_run(self):
        return True
