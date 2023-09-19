import json
import shutil
from pathlib import Path

from dotenv.cli import run_command

from oarepo_cli.site.mixins import SiteWizardStepMixin
from oarepo_cli.utils import run_cmdline
from oarepo_cli.wizard import WizardStep
import jinja2


class CreateViteStep(SiteWizardStepMixin, WizardStep):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def after_run(self):
        vite_directory: Path = self.data.project_dir / ".vite"
        if not vite_directory.exists():
            vite_directory.mkdir()
        self.generate_paths(vite_directory)
        path_data = json.loads((vite_directory / "paths.json").read_text())
        # self.generate_package_json(vite_directory, path_data)
        # self.install_package_json(vite_directory)
        self.generate_vite_config(vite_directory, path_data)
        self.generate_html_entry_points(vite_directory, path_data)
        self.generate_index_html(vite_directory, path_data)
        self.create_repo_symlink(vite_directory)

    def generate_paths(self, vite_directory):
        self.site_support.call_invenio(
            "oarepo",
            "assets",
            "vite",
            self.data.project_dir,
            vite_directory / "paths.json",
        )

    def should_run(self):
        return True

    def generate_package_json(self, vite_directory, path_data):
        package_json_data = {
            "name": "vite-nrpbuilder",
            "private": True,
            "version": "0.0.0",
            "type": "module",
            "scripts": {
                "dev": "vite",
                "build": "vite build",
                "lint": "eslint src --ext js,jsx --report-unused-disable-directives --max-warnings 0",
                "preview": "vite preview",
            },
            "dependencies": path_data["dependencies"]["dependencies"],
            "devDependencies": {
                **path_data["dependencies"]["devDependencies"],
                "@rollup/plugin-alias": "^5.0.0",
                "@rollup/plugin-dynamic-import-vars": "^2.0.3",
                "@rollup/plugin-inject": "^5.0.3",
                "@rollup/plugin-replace": "^5.0.2",
                "@types/react": "^18.0.37",
                "@types/react-dom": "^18.0.11",
                "@vitejs/plugin-react": "^4.0.0",
                "eslint": "^8.38.0",
                "eslint-plugin-react": "^7.32.2",
                "eslint-plugin-react-hooks": "^4.6.0",
                "eslint-plugin-react-refresh": "^0.3.4",
                "jscodeshift": "^0.15.0",
                "less": "^4.1.3",
                "rollup-plugin-copy": "^3.4.0",
                "sass": "^1.63.6",
                "unplugin-lodash-to-lodashes": "^0.2.0",
                "vite": "^4.3.9",
                "vite-plugin-dynamic-import": "^1.5.0",
                "vite-plugin-imp": "^2.4.0",
                "vite-plugin-mock": "^2.9.8",
                "vite-plugin-mock-server": "^1.1.0",
                "vite-plugin-prebundle": "^0.0.4",
                "@vitejs/plugin-basic-ssl": "^@1.0.1",
            },
        }
        with open(vite_directory / "package.json", "w") as f:
            json.dump(package_json_data, f, indent=4, ensure_ascii=False)

    def install_package_json(self, vite_directory):
        run_cmdline(
            "bun",
            "install",
            cwd=vite_directory,
        )

    def render_template(self, template_name, context, out_file):
        env = jinja2.Environment(
            loader=jinja2.loaders.FileSystemLoader(
                [Path(__file__).parent / "templates"]
            ),
            autoescape=True,
        )
        tmpl = env.get_template(template_name)
        rendered = tmpl.render(context)
        out_file.write_text(rendered)

    def generate_vite_config(self, vite_directory, path_data):
        self.render_template(
            "vite.config.js.jinja",
            {
                **path_data,
                "cwd": vite_directory,
            },
            vite_directory / "vite.config.js",
        )

    def generate_html_entry_points(self, vite_directory, path_data):
        entrypoints_path = vite_directory / "entrypoints"
        if not entrypoints_path.exists():
            entrypoints_path.mkdir()

        for ep_name, ep_value in path_data["entries"].items():
            self.render_template(
                "entry_point.html.jinja",
                {"ep_location": ep_value, "ep_name": ep_name},
                entrypoints_path / f"{ep_name}.html",
            )
            self.render_template(
                "entry_point.js.jinja",
                {"ep_location": ep_value, "ep_name": ep_name},
                entrypoints_path / f"{ep_name}.js",
            )

    def generate_index_html(self, vite_directory, path_data):
        self.render_template(
            "index.html.jinja", path_data, vite_directory / "index.html"
        )

    def create_repo_symlink(self, vite_directory):
        repo_path = vite_directory / "repo"
        if not repo_path.exists():
            repo_path.symlink_to("..")
