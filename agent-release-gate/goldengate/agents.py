"""Connecting the gate to an agent.

  py:package.module:function   a Python function that takes the input text and returns the output object
  cmd:<command line>           any program: the gate writes {"input": "..."} to its stdin and reads the
                               output object as JSON from its stdout (exit code 0 = success)
"""

from __future__ import annotations

import importlib
import json
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Callable

STDERR_TAIL_CHARS = 500


class AgentError(RuntimeError):
    """The agent could not be loaded, failed, timed out, or returned something that isn't JSON."""


@dataclass(frozen=True)
class Agent:
    spec: str
    call: Callable[[str, float], Any]  # (input text, timeout in seconds) -> output


def _python_agent(spec: str, target: str) -> Agent:
    module_name, sep, func_name = target.partition(":")
    if not sep or not module_name or not func_name:
        raise AgentError(f"python agent must look like py:package.module:function, got {spec!r}")
    cwd = os.getcwd()
    if cwd not in sys.path:
        sys.path.insert(0, cwd)
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        raise AgentError(f"cannot import {module_name!r}: {exc}") from None
    func = getattr(module, func_name, None)
    if not callable(func):
        raise AgentError(f"{module_name!r} has no function {func_name!r}")
    # Timeouts for Python agents are enforced by the runner, which calls them on a worker thread.
    return Agent(spec=spec, call=lambda text, _timeout: func(text))


def _command_agent(spec: str, command: str) -> Agent:
    argv = shlex.split(command)
    if not argv:
        raise AgentError("command agent needs a command after 'cmd:'")

    def call(text: str, timeout: float) -> Any:
        try:
            proc = subprocess.run(
                argv,
                input=json.dumps({"input": text}),
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError:
            raise AgentError(f"command not found: {argv[0]}") from None
        except subprocess.TimeoutExpired:
            raise AgentError(f"timed out after {timeout:g}s") from None
        if proc.returncode != 0:
            tail = proc.stderr.strip()[-STDERR_TAIL_CHARS:]
            raise AgentError(f"exited with code {proc.returncode}" + (f": {tail}" if tail else ""))
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise AgentError(f"stdout is not JSON ({exc.msg})") from None

    return Agent(spec=spec, call=call)


def load_agent(spec: str) -> Agent:
    kind, sep, target = spec.partition(":")
    if sep and kind == "py":
        return _python_agent(spec, target)
    if sep and kind == "cmd":
        return _command_agent(spec, target)
    raise AgentError(f"agent must start with 'py:' or 'cmd:', got {spec!r}")
