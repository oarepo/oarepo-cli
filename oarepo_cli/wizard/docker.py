import sys


from oarepo_cli.utils import run_nrp_in_docker_compose, run_nrp_in_docker
from oarepo_cli.wizard import WizardStep


class RunInContainerStep(WizardStep):
    def __init__(self, steps, in_compose=True):
        self.steps = steps or []
        self.in_compose = in_compose

    def should_run(self):
        return True

    def run(self, single_step=None):
        cmd = sys.argv[1:]
        for idx, c in enumerate(cmd):
            if c == '--project-dir':
                cmd[idx+1] = '/repository'
                break
        else:
            cmd.extend(['--project-dir', '/repository'])
        for step in self.steps:
            if single_step and step != single_step:
                continue
            cmd.append('--step')
            cmd.append(step.name)
        print(cmd)
        if self.in_compose:
            run_nrp_in_docker_compose(self.data.project_dir / self.data['site_dir'],
                                      *cmd)
        else:
            run_nrp_in_docker(self.data.project_dir, *cmd)

    @property
    def name(self):
        return "_".join(x.name for x in self.steps)


class DockerRunner:
    def __init__(self, running_in_container, use_container):
        self._running_in_container = running_in_container
        self._use_container = use_container

    def wrap_docker_steps(self, *steps, in_compose=True):
        if not self._use_container or self._running_in_container:
            return steps
        return [RunInContainerStep(steps, in_compose=in_compose)]