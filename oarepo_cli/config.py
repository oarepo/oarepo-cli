from io import StringIO
from pathlib import Path

import yaml
from deepmerge import always_merger


class Config:
    def __init__(self):
        self.config = {}

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

    def on_changed(self):
        pass


class MonorepoConfig(Config):
    type = "monorepo"

    def __init__(self, path: Path, section=["config"]):
        super().__init__()
        self.path = path
        self.existing = False
        if not section:
            section = []
        elif isinstance(section, str):
            section = [section]
        self.section_path = tuple(section)
        self.whole_data = {}
        self._load_section()

    def load(self):
        with open(self.path, "r") as f:
            data = yaml.safe_load(f)
            self.whole_data = data
            self._load_section()
            self.existing = True

    def _load_section(self):
        data = self.whole_data
        for s in self.section_path:
            data = data.setdefault(s, {})
        self.config = data

    def save(self):
        data = {**self.whole_data, "type": self.type}
        # just try to dump so that if that is not successful we do not overwrite the config
        sio = StringIO()
        yaml.safe_dump(data, sio)

        # and real dump here
        if self.path.parent.exists():
            with open(self.path, "w") as f:
                f.write(sio.getvalue())

    def on_changed(self):
        if self.path.parent.exists():
            self.save()

    def _section(self, name, default=None):
        name = name.split(".")
        d = self.whole_data
        for n in name[:-1]:
            d = d.get(n, {})
        return d.get(name[-1], default)

    def get(self, item, default=None):
        if "." in item:
            return self._section(item, default)
        return super().get(item, default)

    @property
    def section(self):
        return self.section_path[-1]

    @property
    def project_dir(self):
        return self.path.parent.resolve()

    def merge_config(self, config_data, top=False):
        if top:
            always_merger.merge(self.whole_data, config_data)
            self._load_section()
            self.save()
        else:
            always_merger.merge(self.config, config_data)
