#!/bin/bash

# just for testing

set -e

BUILDPLATFORM=linux/arm64/v8

(
    DOCKER_BUILDKIT=1 docker build . --no-cache --target production \
      --build-arg REPOSITORY_SITE_ORGANIZATION='' \
      --build-arg REPOSITORY_SITE_NAME='{{cookiecutter.project_shortname}}' \
      --build-arg REPOSITORY_IMAGE_URL='' \
      --build-arg REPOSITORY_AUTHOR='{{cookiecutter.author_name}} <{{cookiecutter.author_email}}>' \
      --build-arg REPOSITORY_GITHUB_URL='{{cookiecutter.github_repo}}' \
      --build-arg REPOSITORY_URL='{{cookiecutter.project_site}}' \
      --build-arg REPOSITORY_DOCUMENTATION='{{cookiecutter.project_site}}documentation' \
      --build-arg BUILDPLATFORM=$BUILDPLATFORM \
      -t cesnet/mytest:11 \
      -t cesnet/mytest:latest -f ./sites/mysite/docker/Dockerfile.production
)