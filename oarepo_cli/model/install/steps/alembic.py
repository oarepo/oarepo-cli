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

        def get_revision_number(stdout_str, file_suffix):
            mtch = re.search(f"(\w{{12}}){file_suffix}", stdout_str)
            if not mtch:
                raise ValueError(
                    "Revision number was not found in revision create stdout"
                )
            return mtch.group(1)

        def get_revision_names(revision_message):
            file_name = revision_message[0].lower() + revision_message[1:]
            file_name = "_" + file_name.replace(" ", "_")
            if file_name[-1] == ".":
                file_name = file_name[:-1]

            file_name = file_name[
                :30
            ]  # there seems to be maximum length for the file name
            idx = file_name.rfind("_")
            file_name = file_name[:idx]  # and all words after it are cut
            return revision_message, file_name

        def rewrite_revision_file(new_id_number, current_revision_id):
            files = list(alembic_path.iterdir())
            files_with_this_revision_id = [
                file_name
                for file_name in files
                if current_revision_id in str(file_name)
            ]

            if not files_with_this_revision_id:
                raise ValueError(
                    "Alembic file rewrite couldn't find the generated revision file"
                )

            if len(files_with_this_revision_id) > 1:
                raise ValueError(
                    "More alembic files with the same revision number found"
                )

            target_file = str(files_with_this_revision_id[0])
            new_id = f"{revision_id_prefix}_{new_id_number}"
            with open(target_file, "r") as f:
                file_text = f.read()
                file_text = file_text.replace(
                    f"revision = '{current_revision_id}'", f"revision = '{new_id}'"
                )
            with open(target_file.replace(current_revision_id, new_id), "w") as f:
                f.write(file_text)
            os.remove(target_file)

        if filecount < 2:
            # alembic has not been initialized yet ...
            self.site_support.call_invenio(
                "alembic", "upgrade", "heads", cwd=self.site_dir
            )
            # create model branch
            revision_message, file_revision_name_suffix = get_revision_names(
                f"Create {branch} branch for {self.data['model_package']}."
            )
            new_revision = get_revision_number(
                self.site_support.call_invenio(
                    "alembic",
                    "revision",
                    revision_message,
                    "-b",
                    branch,
                    "-p",
                    "dbdbc1b19cf2",
                    "--empty",
                    cwd=self.site_dir,
                    grab_stdout=True,
                ),
                file_revision_name_suffix,
            )

            rewrite_revision_file("1", new_revision)

            self.fix_sqlalchemy_utils(alembic_path)
            self.site_support.call_invenio(
                "alembic", "upgrade", "heads", cwd=self.site_dir
            )

            revision_message, file_revision_name_suffix = get_revision_names(
                "Initial revision."
            )
            new_revision = get_revision_number(
                self.site_support.call_invenio(
                    "alembic",
                    "revision",
                    revision_message,
                    "-b",
                    branch,
                    cwd=self.site_dir,
                    grab_stdout=True,
                ),
                file_revision_name_suffix,
            )

            rewrite_revision_file(
                "2", new_revision
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

            revision_message, file_revision_name_suffix = get_revision_names(
                "Nrp install revision."
            )
            self.site_support.call_invenio("alembic", "upgrade", "heads")
            new_revision = get_revision_number(
                self.site_support.call_invenio(
                    "alembic",
                    "revision",
                    revision_message,
                    "-b",
                    branch,
                    grab_stdout=True,
                ),
                file_revision_name_suffix,
            )
            rewrite_revision_file(new_file_number, new_revision)

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
