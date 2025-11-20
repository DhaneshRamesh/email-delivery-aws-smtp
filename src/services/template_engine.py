"""Email template rendering powered by Jinja2."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "templates"
TEMPLATE_DIR.mkdir(exist_ok=True)

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def render_template(template_name: str, **context: Any) -> str:
    """Render a template file with the provided context."""

    template = _env.get_template(template_name)
    return template.render(**context)
