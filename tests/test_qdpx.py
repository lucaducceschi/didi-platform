import io
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest
from lxml import etree

from src.ui.qdpx import NAMESPACE, build_qdpx

XSD_PATH = Path(__file__).parent / "fixtures" / "refi_qda_project.xsd"
NS = {"q": NAMESPACE}


def make_doc(corpus_id="a1", **overrides):
    doc = {
        "corpus_id": corpus_id,
        "name": f"2025-05-01 Salto.bz [de] {corpus_id}",
        "text": "Text.",
        "citation": "Autor (2025). Titel. Salto.bz.",
        "source": "Salto.bz",
        "variety": "German (de)",
        "publish_date": "2025-05-01",
        "author": "Autor",
        "category": "Politik",
        "url": "https://example.org/a?x=1&y=2",
    }
    doc.update(overrides)
    return doc


def read_project(data):
    archive = zipfile.ZipFile(io.BytesIO(data))
    return archive, ET.fromstring(archive.read("project.qde"))


def test_output_validates_against_refi_schema():
    data = build_qdpx("Test & <export>", [make_doc("a1"), make_doc("a2", category=None)])
    archive = zipfile.ZipFile(io.BytesIO(data))
    schema = etree.XMLSchema(etree.parse(str(XSD_PATH)))
    document = etree.fromstring(archive.read("project.qde"))
    assert schema.validate(document), schema.error_log


def test_empty_export_is_refused():
    with pytest.raises(ValueError):
        build_qdpx("Empty", [])


@pytest.mark.parametrize("text", [
    "Gherdëina dlëijia àéü",
    unicodedata.normalize("NFD", "Gherdëina dlëijia"),
    "Line one\r\nLine two\n\nLine three",
    "Emoji 🙂 here",
    "  leading and trailing  \n",
])
def test_text_is_stored_byte_for_byte(text):
    archive, project = read_project(build_qdpx("T", [make_doc(text=text)]))
    source = project.find("q:Sources/q:TextSource", NS)
    path = source.get("plainTextPath").replace("internal://", "sources/")
    assert archive.read(path) == text.encode("utf-8")


def test_metadata_reaches_variables_and_sets():
    _, project = read_project(build_qdpx("T", [make_doc("a1"), make_doc("a2", variety="Italian (it)")]))
    names = {v.get("guid"): v.get("name") for v in project.findall("q:Variables/q:Variable", NS)}
    first = project.find("q:Sources/q:TextSource", NS)
    values = {
        names[v.find("q:VariableRef", NS).get("targetGUID")]: v.find("q:TextValue", NS).text
        for v in first.findall("q:VariableValue", NS)
    }
    assert values["corpus_id"] == "a1"
    assert values["url"] == "https://example.org/a?x=1&y=2"
    sets = {s.get("name"): len(s.findall("q:MemberSource", NS)) for s in project.findall("q:Sets/q:Set", NS)}
    assert sets == {"Source: Salto.bz": 2, "Variety: German (de)": 1, "Variety: Italian (it)": 1}


def test_guids_are_stable_across_exports():
    guids = [
        read_project(build_qdpx("T", [make_doc("a1")]))[1].find("q:Sources/q:TextSource", NS).get("guid")
        for _ in range(2)
    ]
    assert guids[0] == guids[1]


def test_duplicate_names_are_made_unique():
    _, project = read_project(build_qdpx("T", [make_doc("a1", name="Same"), make_doc("a2", name="Same")]))
    assert [s.get("name") for s in project.findall("q:Sources/q:TextSource", NS)] == ["Same", "Same (2)"]


def test_control_characters_in_metadata_do_not_break_xml():
    _, project = read_project(build_qdpx("T", [make_doc(name="Bad\x0btitle", author="Au\x01tor")]))
    assert project.find("q:Sources/q:TextSource", NS).get("name") == "Badtitle"
