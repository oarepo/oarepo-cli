import sys

import yaml

from oarepo_cli.config import MonorepoConfig
from oarepo_cli.utils import run_nrp_in_docker, run_nrp_in_docker_compose
from oarepo_cli.wizard import WizardStep


class RunInContainerStep(WizardStep):
    def __init__(self, steps, in_compose=True):
        self.steps = steps or []
        self.in_compose = in_compose

    def should_run(self):
        return True

    @property
    def site_support(self):
        return self.root.site_support

    def run(self, single_step=None):
        cmd = sys.argv[1:]
        # remove project dir as it is added by docker itself
        for idx, c in enumerate(cmd):
            if c == "--project-dir":
                cmd.pop(idx)
                cmd.pop(idx)
                break
        for step in self.steps:
            if single_step and step != single_step:
                continue
            cmd.append("--step")
            cmd.append(step.name)
        if self.in_compose:
            run_nrp_in_docker_compose(self.site_support.site_dir, *cmd)
        else:
            run_nrp_in_docker(self.data.project_dir, *cmd)

    @property
    def name(self):
        return "_".join(x.name for x in self.steps)


class DockerRunner:
    def __init__(self, cfg: MonorepoConfig, no_input):
        self.cfg = cfg
        self.no_input = no_input

        # load user config
        user_config_path = cfg.path.parent / ".oarepo-user.yaml"
        if user_config_path.exists():
            with open(user_config_path, "r") as f:
                user_config = yaml.safe_load(f)
        else:
            user_config = {}

        # if not overriden by user, load from user config file
        if self.use_docker is None:
            cfg.use_docker = user_config.get("use_docker", None)

        # if user has not yet selected if running through docker, force
        if self.use_docker is None and not self.running_in_docker and not self.no_input:
            cfg.use_docker = (
                input(
                    "I can run all the steps inside a container. Should I do so? [y/n]"
                )
                == "y"
            )
            user_config["use_docker"] = cfg.use_docker
            # write
            with open(user_config_path, "w") as f:
                yaml.safe_dump(user_config, f)

    @property
    def running_in_docker(self):
        return self.cfg.running_in_docker

    @property
    def use_docker(self):
        return self.cfg.use_docker

    def wrap_docker_steps(self, *steps, in_compose=True):
        if not self.use_docker or self.running_in_docker:
            return steps
        return [RunInContainerStep(steps, in_compose=in_compose)]
