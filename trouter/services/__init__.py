"""System service adapters.

Each module renders generated config from a Jinja2 template and knows how to
(re)load the corresponding service. Rendering and reloading are separate so the
TransactionManager can snapshot generated output before any service is touched.

On a non-Pi dev box the `systemctl`/`nft` calls simply fail quietly; generation
still works so the templates can be inspected and unit-tested.
"""
import os
import subprocess

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .. import config

_env = Environment(
    loader=FileSystemLoader(config.SYSTEM_TEMPLATES),
    autoescape=select_autoescape(enabled_extensions=()),
    trim_blocks=True, lstrip_blocks=True,
)


def render(template_name, **ctx):
    return _env.get_template(template_name).render(**ctx)


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write(content)
    os.replace(tmp, path)        # atomic


def run(args, timeout=15):
    """Run a system command, returning (rc, output). Never raises."""
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout + p.stderr)
    except (FileNotFoundError, subprocess.SubprocessError) as e:
        return 127, str(e)
