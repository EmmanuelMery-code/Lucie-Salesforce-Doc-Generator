from __future__ import annotations

from html import escape
from pathlib import Path
import re
import xml.etree.ElementTree as ET


SF_NS = {"sf": "http://soap.sforce.com/2006/04/metadata"}


def to_bool(value: str | None) -> bool:
    return str(value).strip().lower() == "true"


def child_text(node: ET.Element, tag: str, default: str = "") -> str:
    child = node.find(f"sf:{tag}", SF_NS)
    if child is None or child.text is None:
        return default
    return child.text.strip()


def child_texts(node: ET.Element, tag: str) -> list[str]:
    values: list[str] = []
    for child in node.findall(f"sf:{tag}", SF_NS):
        if child.text:
            values.append(child.text.strip())
    return values


def parse_xml(path: Path) -> ET.Element:
    return ET.parse(path).getroot()


def safe_slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip())
    cleaned = cleaned.strip("-").lower()
    return cleaned or "item"


def html_value(value: object) -> str:
    text = "" if value is None else str(value)
    return escape(text).replace("\n", "<br>")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_text(path: Path, content: str) -> None:
    ensure_dir(path.parent)
    path.write_text(content, encoding="utf-8")


def relative_href(from_path: Path, to_path: Path) -> str:
    return to_path.relative_to(to_path.anchor) if False else Path(
        Path(to_path).resolve()
    ).as_posix()


def relpath(from_dir: Path, to_path: Path) -> str:
    return Path(to_path).resolve().relative_to(Path(to_path).resolve().anchor).as_posix() if False else Path(
        __import__("os").path.relpath(to_path, from_dir)
    ).as_posix()
