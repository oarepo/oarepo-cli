"""JS/CSS Webpack bundles for {{cookiecutter.project_name}}."""

from invenio_assets.webpack import WebpackThemeBundle

theme = WebpackThemeBundle(
    __name__,
    "assets",
    default="semantic-ui",
    themes={
        "semantic-ui": dict(
            entry={
                # Add your webpack entrypoints
            },
            devDependencies={
                "eslint": ">=8.0.0",
                "eslint-config-react-app": ">=7.0.0",
                "prettier": ">=2.8.0",
                "eslint-config-prettier": ">=8.8.0",
            },
        ),
    },
)
