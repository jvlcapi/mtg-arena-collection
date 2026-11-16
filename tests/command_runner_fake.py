"""A stand-in for subprocess.run that records each command instead of running it."""

import subprocess


class RecordingCommandRunner:
    def __init__(self, return_codes=None, stdout="", stderr="", missing_program=False):
        self.return_codes = dict(return_codes or {})
        self.stdout = stdout
        self.stderr = stderr
        self.missing_program = missing_program
        self.calls = []

    def __call__(self, arguments, **options):
        self.calls.append((list(arguments), options))
        if self.missing_program:
            raise FileNotFoundError(arguments[0])
        return_code = self.return_codes.get(tuple(arguments[:2]), self.return_codes.get("default", 0))
        return subprocess.CompletedProcess(arguments, return_code, self.stdout, self.stderr)

    @property
    def commands(self):
        return [arguments for arguments, _ in self.calls]
