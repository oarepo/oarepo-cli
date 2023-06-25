from collections import defaultdict

from .base import BaseFormatStep


class FormatPythonStep(BaseFormatStep):
    def format_paths(self, model_paths, ui_paths, local_paths, site_paths):
        python_source_paths = [*model_paths, *ui_paths, *local_paths, *site_paths]
        self.run_autoflake(python_source_paths, exclude=[])
        self.run_isort(python_source_paths)
        self.run_black(python_source_paths)

    def run_autoflake(self, dirs, exclude):
        from autoflake import find_files, fix_file

        files = list(find_files([*dirs], True, exclude))

        for file_name in files:
            try:
                fix_file(
                    file_name,
                    args=defaultdict(
                        lambda: None,
                        in_place=True,
                        remove_all_unused_imports=True,
                        write_to_stdout=False,
                        verbose=True,
                    ),
                )
            except Exception as e:
                print(f"Error in autoflaking {file_name}: {e}")

    def run_isort(self, dirs):
        from isort.main import main

        main(["--profile", "black", *[str(x) for x in dirs]])

    def run_black(self, dirs):
        import black

        black.main([*[str(x) for x in dirs]], standalone_mode=False)
