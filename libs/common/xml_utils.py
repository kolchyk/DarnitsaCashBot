from __future__ import annotations

from typing import Any
from xml.etree import ElementTree as ET


class XMLParseError(Exception):
    """Raised when inbound XML payloads cannot be parsed."""


def parse_xml_document(xml_text: str) -> ET.Element:
    try:
        return ET.fromstring(xml_text)
    except ET.ParseError as exc:  # pragma: no cover - bubble up for callers
        raise XMLParseError(str(exc)) from exc


def flatten_xml(element: ET.Element, prefix: str | None = None) -> dict[str, str]:
    """Convert an XML tree into a flat dict preserving dotted paths."""

    path = element.tag if prefix is None else f"{prefix}.{element.tag}"
    data: dict[str, str] = {}

    # include attributes for traceability
    for attr_key, attr_value in element.attrib.items():
        data[f"{path}@{attr_key}"] = attr_value

    children = list(element)
    if not children:
        text = (element.text or "").strip()
        if text:
            data[path] = text
        return data

    for child in children:
        data.update(flatten_xml(child, path))

    return data


__all__ = ["flatten_xml", "parse_xml_document", "XMLParseError"]

