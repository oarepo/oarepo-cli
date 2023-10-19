import json
import os
import re
import shutil
import sys
import traceback
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

        self.generate_package_json(self.data.project_dir, path_data)
        self.install_package_json(self.data.project_dir)
        self.optimize_paths(self.data.project_dir, path_data)
        self.generate_vite_config(self.data.project_dir, path_data)
        self.generate_html_entry_points(vite_directory, path_data)
        self.generate_index_html(vite_directory, path_data)

    def generate_paths(self, vite_directory):
        self.site_support.call_invenio(
            "oarepo",
            "assets",
            "vite",
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
                "@rollup/plugin-commonjs": "^25.0.5",
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
        aliases = {}
        for name, alias in path_data["aliases"].items():
            if alias.startswith("./node_modules"):
                aliases[name] = alias
            else:
                aliases[name] = str((vite_directory / alias).resolve())
                # keep tailing / which is removed by resolve()
                if alias.endswith("/") and not aliases[name].endswith("/"):
                    aliases[name] += "/"

        self.render_template(
            "vite.config.js.jinja",
            {
                **path_data,
                "cwd": vite_directory,
                "aliases": [
                    (
                        "~admin-lte/dist/css/AdminLTE",
                        "./node_modules/admin-lte/dist/css/AdminLTE.css",
                    ),
                    (
                        "~prismjs/themes/prism",
                        "./node_modules/prismjs/themes/prism.css",
                    ),
                    (
                        "~admin-lte/dist/css/skins/skin-blue",
                        "./node_modules/admin-lte/dist/css/skins/skin-blue.css",
                    ),
                    ("~(.*/css/.*)", "node_modules/$1.css"),
                    *sorted(aliases.items(), key=lambda x: (-len(x[0]), x[0])),
                ],
            },
            vite_directory / "vite.config.js",
        )

    def generate_html_entry_points(self, vite_directory, path_data):
        entrypoints_path = vite_directory
        if not entrypoints_path.exists():
            entrypoints_path.mkdir()

        for ep_name, ep_value in path_data["entries"].items():
            self.render_template(
                "entry_point.html.jinja",
                {"ep_location": ep_value, "ep_name": ep_name},
                entrypoints_path / f"{ep_name}.html",
            )
            ep_location = ep_value
            if ep_location.startswith("/"):
                # make absolute import relative
                ep_location = os.path.relpath(ep_location, vite_directory)
            else:
                ep_location = "../" + ep_location

            ep_location = ep_location.replace("/./", "/")
            self.render_template(
                "entry_point.js.jinja",
                {"ep_location": ep_location, "ep_name": ep_name},
                entrypoints_path / f"{ep_name}.js",
            )

    def generate_index_html(self, vite_directory, path_data):
        self.render_template(
            "index.html.jinja", path_data, vite_directory / "index.html"
        )

    def optimize_paths(self, vite_directory, path_data):
        alias_path_mapping = self.convert_to_node_modules(
            vite_directory, path_data, path_data["base_paths"]
        )

        for entry, path in list(sorted(path_data["entries"].items())):
            for original_path, new_path in sorted(
                alias_path_mapping, key=lambda x: (-len(x[0]), x[0])
            ):
                if path.startswith(original_path):
                    path = path[len(original_path) :]
                    if path[0] == "/":
                        path = path[1:]
                    path_data["entries"][entry] = f"{new_path}/{path}"
                    break
            else:
                new_path = self.try_to_move_to_node_modules(
                    vite_directory, path, path_data["base_paths"]
                )
                if new_path:
                    path_data["entries"][entry] = new_path

    def convert_to_node_modules(self, vite_directory, path_data, base_paths):
        alias_path_mapping = {}
        for alias_name, alias_path in list(path_data["aliases"].items()):
            new_alias_path = self.try_to_move_to_node_modules(
                vite_directory, alias_path, base_paths
            )
            if new_alias_path:
                path_data["aliases"][alias_name] = new_alias_path
                alias_path_mapping[alias_path] = new_alias_path

        return list(alias_path_mapping.items())

    def try_to_move_to_node_modules(self, vite_directory, source_path, base_paths):
        if source_path.startswith("repo:"):
            # repository is here
            resolved_path = str(
                (vite_directory / source_path.removeprefix("repo:")).resolve()
            )
            # keep tailing / which is removed by resolve()
            if source_path.endswith("/") and not resolved_path.endswith("/"):
                resolved_path += "/"
            return resolved_path
        if source_path.startswith("relative:"):
            # can not move, it is just here (relative:node_modules, for example)
            return source_path.removeprefix("relative:")
        if source_path.startswith("python:"):
            # let's try to move the python
            return self.move_site_package_to_node_modules(
                vite_directory, source_path, base_paths
            )
        else:
            # it is a prefixed path, lookup the prefix and never move it to
            # node_modules, as this is a "work in progress" library and we
            # do not want to optimize it
            prefix, source_path = source_path.split(":", maxsplit=1)
            abs_path = os.path.join(base_paths[prefix], source_path)
            relpath = os.path.relpath(abs_path, vite_directory)
            return relpath

    def move_site_package_to_node_modules(
        self, vite_directory, source_path, base_paths
    ):
        path_from_site_packages = source_path.removeprefix("python:")

        match = re.match(
            r"^([^/]+.*?)/(semantic-ui/)(.*)",
            path_from_site_packages,
        )
        if not match:
            # not a candidate for moving to node modules
            raise Exception(
                f"Can not move the following package to node modules: {source_path}"
            )

        python_module = match.group(1)
        semantic_ui = match.group(2) or ""
        after_semantic_ui = match.group(3)
        node_package_name = python_module.split("/")[0]
        path_to_copy = f"{base_paths['python']}/{python_module}/{semantic_ui}"

        if Path(path_to_copy).exists():
            self.convert_to_node_package(
                vite_directory,
                node_package_name=node_package_name,
                path_to_copy=path_to_copy,
            )
        else:
            return path_to_copy

        return f"./node_modules/{node_package_name}/{after_semantic_ui}"

    def convert_to_node_package(
        self,
        vite_directory,
        *,
        node_package_name,
        path_to_copy,
    ):
        target_module = vite_directory / "node_modules" / node_package_name

        copy_tree_and_replace(
            path_to_copy, target_module, JAVASCRIPT_IMPORT_REPLACEMENTS
        )

        package_json = Path(target_module) / "package.json"
        if not package_json.exists():
            # create empty package.json
            package_json_data = {
                "name": node_package_name,
                "version": "0.1.0",
                "author": "nrp client",
            }
            package_json.write_text(json.dumps(package_json_data, indent=4))


def copy_tree_and_replace(source: Path, destination: Path, replacements):
    for source_path in Path(source).iterdir():
        destination_path = destination / source_path.name
        if source_path.is_dir():
            destination_path.mkdir(exist_ok=True, parents=True)
            copy_tree_and_replace(source_path, destination_path, replacements)
        else:
            try:
                data = load_or_replace_file(source_path)
                transformed_lines = []
                for line in data.split("\n"):
                    for k, v in replacements:
                        line = re.sub(k, v, line)
                    transformed_lines.append(line)
                destination_path.write_text("\n".join(transformed_lines))
            except:
                # print(f"Copying binary file {source_path}")
                destination_path.write_bytes(source_path.read_bytes())


def load_or_replace_file(source_path):
    for pth in FILE_REPLACEMENTS:
        if str(source_path).endswith(pth):
            return FILE_REPLACEMENTS[pth]
    return source_path.read_text("utf-8")


JAVASCRIPT_IMPORT_REPLACEMENTS = [
    (
        r'^import ([_a-zA-Z]+) from "lodash/(.*)";?$',
        r'import {\2 as \1} from "lodash-es";',
    ),
    (
        r"^var ([^=]*)=\s*require\('lodash/([^']*)'\);?$",
        r'import {\2 as \1} from "lodash-es";',
    ),
    (
        r'^var ([^=]*)=\s*require\("lodash/([^"]*)"\);?$',
        r'import {\2 as \1} from "lodash-es";',
    ),
]

FILE_REPLACEMENTS = {
    "translations/invenio_search_ui/messages/index.js": """
import TRANSLATE_CS from "./cs/translations.json";
import TRANSLATE_EN from "./en/translations.json";

export const translations = {
  cs: { translation: TRANSLATE_CS },
  en: { translation: TRANSLATE_EN },
};
    """
}
