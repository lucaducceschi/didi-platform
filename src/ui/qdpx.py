"""Build REFI-QDA project files (.qdpx) for import into MAXQDA."""

import io
import re
import uuid
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from typing import Any, Dict, Iterable

NAMESPACE = "urn:QDA-XML:project:1.0"
GUID_NAMESPACE = uuid.UUID("6f1c2f0e-5d3b-5a7e-9c41-0d1d1d1a2b3c")
# Every variable is Text: ISO dates still sort correctly, and how MAXQDA treats Date is untested.
VARIABLES = ("corpus_id", "source", "variety", "publish_date", "author", "category", "url")
_INVALID_XML_RE = re.compile(r"[^\t\n\r\x20-퟿-�\U00010000-\U0010FFFF]")

ET.register_namespace("", NAMESPACE)


def _tag(name: str) -> str:
    return f"{{{NAMESPACE}}}{name}"


def _guid(kind: str, key: str) -> str:
    """Return a GUID that stays the same across exports, so later imports can match on it."""
    return str(uuid.uuid5(GUID_NAMESPACE, f"{kind}:{key}"))


def _xml_text(value: Any) -> str:
    return _INVALID_XML_RE.sub("", str(value or ""))


def build_qdpx(project_name: str, documents: Iterable[Dict[str, Any]]) -> bytes:
    """
    Package documents as a .qdpx archive.

    Each document needs: corpus_id, name, text, citation, source, variety, publish_date,
    author, category, url. Text is stored unchanged, because coded segments will refer to
    its character positions.
    """
    documents = list(documents)
    if not documents:
        raise ValueError("A REFI-QDA project needs at least one source")

    created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    user_guid = _guid("user", "DIDI Platform")
    project = ET.Element(_tag("Project"), {
        "name": _xml_text(project_name),
        "origin": "DIDI Platform",
        "creatingUserGUID": user_guid,
        "creationDateTime": created,
    })
    users = ET.SubElement(project, _tag("Users"))
    ET.SubElement(users, _tag("User"), {"guid": user_guid, "name": "DIDI Platform"})

    variables = ET.SubElement(project, _tag("Variables"))
    for name in VARIABLES:
        ET.SubElement(variables, _tag("Variable"), {
            "guid": _guid("variable", name),
            "name": name,
            "typeOfVariable": "Text",
        })

    sources = ET.SubElement(project, _tag("Sources"))
    sets: Dict[str, list] = {}
    used_names: Dict[str, int] = {}
    files = []
    for doc in documents:
        source_guid = _guid("article", doc["corpus_id"])
        name = _xml_text(doc["name"])
        used_names[name] = used_names.get(name, 0) + 1
        if used_names[name] > 1:
            name = f"{name} ({used_names[name]})"

        source = ET.SubElement(sources, _tag("TextSource"), {
            "guid": source_guid,
            "name": name,
            "plainTextPath": f"internal://{source_guid}.txt",
            "creatingUser": user_guid,
            "creationDateTime": created,
        })
        ET.SubElement(source, _tag("Description")).text = _xml_text(doc["citation"])
        for variable in VARIABLES:
            value = ET.SubElement(source, _tag("VariableValue"))
            ET.SubElement(value, _tag("VariableRef"), {"targetGUID": _guid("variable", variable)})
            ET.SubElement(value, _tag("TextValue")).text = _xml_text(doc[variable])

        files.append((f"sources/{source_guid}.txt", doc["text"].encode("utf-8")))
        sets.setdefault(f"Variety: {doc['variety']}", []).append(source_guid)
        sets.setdefault(f"Source: {doc['source']}", []).append(source_guid)

    sets_element = ET.SubElement(project, _tag("Sets"))
    for set_name, members in sorted(sets.items()):
        set_element = ET.SubElement(sets_element, _tag("Set"), {
            "guid": _guid("set", set_name),
            "name": _xml_text(set_name),
        })
        for member in members:
            ET.SubElement(set_element, _tag("MemberSource"), {"targetGUID": member})

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("project.qde", ET.tostring(project, encoding="utf-8", xml_declaration=True))
        for path, content in files:
            archive.writestr(path, content)
    return buffer.getvalue()
