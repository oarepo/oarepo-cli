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
                "eslint": "^8.0.0",
                "eslint-config-react-app": "^7.0.0",
                "prettier": "^2.8.0",
                "eslint-config-prettier": "^8.8.0",
                "@typescript-eslint/eslint-plugin": "^5.0.0",
                "@typescript-eslint/parser": "^5.0.0",
                "typescript": "^5.0.0",
                "@babel/plugin-proposal-private-property-in-object": "^7.0.0",
            },
            aliases={},
        ),
    },
)
