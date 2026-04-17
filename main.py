import re
import csv
import httpx
import datetime
import dataclasses
import hashlib
from bs4 import BeautifulSoup
from bs4.element import Tag

NAME_CODE = "0"
ALIAS_CODE = "1"


@dataclasses.dataclass
class Person:
    id: int
    name: str
    aliases: list[str]
    birth_date: str | None
    location: str | None

    def to_list(self, alias_idx: int | None = None) -> list[str]:
        if alias_idx is not None:
            name = self.aliases[alias_idx]
        else:
            name = self.name

        return [
            str(self.id),
            name,
            self.birth_date or "-",
            self.location or "-",
            ALIAS_CODE if alias_idx is not None else NAME_CODE,
            hashlib.sha1(name.encode("utf-8")).hexdigest(),
        ]


URL = "https://www.fedsfm.ru/documents/terrorists-catalog-portal-act"


def get_html(client: httpx.Client) -> str:
    response = client.get(URL, timeout=30.0)
    response.raise_for_status()
    return response.text


def parse_html(raw: str) -> Tag | None:
    soup = BeautifulSoup(raw, "lxml")
    russianFL = soup.find(id="russianFL")
    return russianFL


PERSON_PATTERN = re.compile(
    r"^(?P<id>\d+)\.\s+"  # ID
    r"(?P<name>[^,*(\d]+?)\*?\s*,\s*"  # Имя
    r"(?:\((?P<aliases>[^)]+)\)\s*,\s*)?"  # Псевдонимы (опционально)
    r"(?:(?P<birth_date>\d{2}\.\d{2}\.\d{4})\s+г\.р\.\s*)?"  # Дата (опционально)
    r"(?:\s*,\s*(?P<location>.*))?"  # Локация (забирает всё оставшееся)
    r"\s*;$"
)


def normalize_location(value: str | None) -> str | None:
    if not value:
        return None
    parts = [cleaned for part in value.split(",") if (cleaned := part.strip())]

    return ", ".join(parts) if parts else None


def parse_person(text: str) -> Person | None:
    text = re.sub(r"\s+", " ", text).strip()
    match = PERSON_PATTERN.fullmatch(text)
    if not match:
        return None

    data = match.groupdict()
    aliases = [a.strip() for a in data["aliases"].split(";")] if data["aliases"] else []

    birth_date: str | None = None
    if data["birth_date"]:
        raw_birth_date = data["birth_date"]
        birth_date = datetime.datetime.strptime(raw_birth_date, "%d.%m.%Y").strftime(
            "%Y-%m-%d"
        )

    location = normalize_location(data["location"])

    return Person(
        id=int(data["id"]),
        name=data["name"].strip(),
        aliases=aliases,
        birth_date=birth_date,
        location=location,
    )


def extract_people_from_html(parsed: Tag | None) -> list[Person]:
    rows = []
    if parsed is None:
        return rows

    people_list = parsed.select_one("div > ol")
    if people_list is None:
        return rows

    for el in people_list.find_all("li"):
        text = el.get_text(strip=True)
        if not text:
            continue

        person = parse_person(text)
        if person is not None:
            rows.append(person)

    return rows


def save_to_csv(persons: list[Person], filename: str = "persons.csv") -> None:
    with open(filename, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        for person in persons:
            writer.writerow(person.to_list())

            for alias_idx in range(len(person.aliases)):
                writer.writerow(person.to_list(alias_idx=alias_idx))


def main():
    with httpx.Client(verify=False) as client:
        raw = get_html(client=client)

    parsed = parse_html(raw)
    persons = extract_people_from_html(parsed)

    save_to_csv(persons)


if __name__ == "__main__":
    main()
