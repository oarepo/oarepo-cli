class Widget:
    def __init__(self, name, default=None):
        self.name = name
        self.value = None
        self.default = default

    def run(self):
        return self.value
