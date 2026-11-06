from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.database import get_engine
from backend.app.models import Annotation, Code
from backend.app.services.annotations import trim_selection
from tests.test_codebook import make_code

CLIENTS = 10
SEGMENTS_EACH = 50


def distinct_spans(text, ends):
    """Selections ending on whitespace are trimmed, so some of them become the same segment."""
    return len({trim_selection(text, 0, end) for end in ends})


def test_ten_clients_write_at_once_without_losing_anything(world, password_hash, fixture_records):
    from backend.app.models import ProjectMember, User

    with Session(get_engine()) as db:
        for index in range(CLIENTS):
            user = User(username=f"c{index}", display_name=f"C{index}", password_hash=password_hash)
            db.add(user)
            db.flush()
            db.add(ProjectMember(project_id=world.ids["project"], user_id=user.id, role="coder"))
        db.commit()
    clients = [world.make_client(f"c{index}") for index in range(CLIENTS)]
    code = make_code(world, "Shared")
    url = f"{world.url}/articles/fx_de_1/annotations"

    def work(index_and_client):
        index, client = index_and_client
        failures = []
        for number in range(SEGMENTS_EACH):
            response = client.post(url, json={"start": 0, "end": 3 + number % 40, "code_id": code["id"], "memo": f"{index}-{number}"})
            # Repeated spans by one coder return the existing segment.
            if response.status_code not in (200, 201):
                failures.append(response.text)
            if number % 10 == 0:
                created = client.post(f"{world.url}/codes", json={"name": f"Code {index} {number}"})
                if created.status_code != 201:
                    failures.append(created.text)
        return failures

    with ThreadPoolExecutor(CLIENTS) as pool:
        failures = [failure for result in pool.map(work, enumerate(clients)) for failure in result]

    assert failures == []
    with Session(get_engine()) as db:
        text = next(record for record in fixture_records if record["id"] == "fx_de_1")["full_text"]
        ends = [3 + number % 40 for number in range(SEGMENTS_EACH)]
        assert db.scalar(select(func.count()).select_from(Annotation)) == CLIENTS * distinct_spans(text, ends)
        # Five new codes per client, plus the shared one.
        assert db.scalar(select(func.count()).select_from(Code)) == CLIENTS * 5 + 1


def test_two_clients_creating_the_same_code_name_get_one_code(world):
    def create(client):
        return client.post(f"{world.url}/codes", json={"name": "Same"}).status_code

    with ThreadPoolExecutor(2) as pool:
        statuses = sorted(pool.map(create, [world.coder, world.coder2]))
    assert statuses == [201, 409]


def test_segments_saved_during_a_merge_are_not_left_on_the_merged_code(world, fixture_records):
    source = make_code(world, "Source")
    target = make_code(world, "Target")
    url = f"{world.url}/articles/fx_de_1/annotations"

    def save(client):
        return [client.post(url, json={"start": 0, "end": end, "code_id": source["id"]}).status_code for end in range(3, 23)]

    def merge():
        return world.lead.post(f"{world.url}/codes/{source['id']}/merge", json={"target_id": target["id"], "source_revision": 1, "target_revision": 1}).status_code

    with ThreadPoolExecutor(3) as pool:
        saves = [pool.submit(save, world.coder), pool.submit(save, world.coder2)]
        merged = pool.submit(merge)
        assert merged.result() == 200
        assert all(status in (200, 201) for future in saves for status in future.result())

    with Session(get_engine()) as db:
        assert db.scalar(select(func.count()).select_from(Annotation).where(Annotation.code_id == source["id"])) == 0
        text = next(record for record in fixture_records if record["id"] == "fx_de_1")["full_text"]
        expected = 2 * distinct_spans(text, range(3, 23))
        assert db.scalar(select(func.count()).select_from(Annotation).where(Annotation.code_id == target["id"])) == expected
