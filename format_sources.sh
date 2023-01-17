autoflake --in-place --remove-all-unused-imports -r oarepo_cli
isort --profile black oarepo_cli
black oarepo_cli
