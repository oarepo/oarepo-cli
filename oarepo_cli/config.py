from io import StringIO
from pathlib import Path

import yaml


class Config:
    def __init__(self):
        self.config = {}
        self.ok_steps = set()

    def __getitem__(self, item):
        return self.config[item]

    def __setitem__(self, key, value):
        self.config[key] = value
        self.on_changed()

    def __iter__(self):
        return iter(self.config)

    def keys(self):
        return self.config.keys()

    def values(self):
        return self.config.values()

    def items(self):
        return self.config.items()

    def get(self, item, default=None):
        return self.config.get(item, default)

    def setdefault(self, item, default):
        return self.config.setdefault(item, default)

    def set_step_ok(self, step_name):
        self.ok_steps.add(step_name)
        self.on_changed()

    def is_step_ok(self, step_name):
        return step_name in self.ok_steps

    def on_changed(self):
        pass


class MonorepoConfig(Config):
    type = "monorepo"

    def __init__(self, path: Path, section=None):
        super().__init__()
        self.path = path
        self.existing = False
        self.section = tuple(section or [])
        self.whole_data = {}
        self.ok_steps = set()

    def load(self):
        with open(self.path, "r") as f:
            data = yaml.safe_load(f)
            self.whole_data = data
            for s in self.section:
                data = data.get(s, {})
            self.config = data.get('config', {})
            self.ok_steps = set(data.get("ok_steps", []))
            self.existing = True

    def save(self):
        data = {**self.whole_data, "type": self.type}
        dd = data
        for s in self.section:
            dd = dd.setdefault(s, {})
        dd["config"] = self.config
        dd["ok_steps"] = self.ok_steps
        # just try to dump so that if that is not successful we do not overwrite the config
        sio = StringIO()
        yaml.safe_dump(data, sio)

        # and real dump here
        with open(self.path, "w") as f:
            f.write(sio.getvalue())

    def on_changed(self):
        if self.path.parent.exists():
            self.save()

    def _section(self, name, default=None):
        name = name.split('.')
        d = self.whole_data
        for n in name[:-1]:
            d = d.get(n, {})
        return d.get(name[-1], None)

    def get(self, item, default=None):
        if '.' in item:
            return self._section(item, default)
        return super().get(item, default)
