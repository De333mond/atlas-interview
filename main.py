import re
import httpx
import datetime
import dataclasses
import hashlib
from bs4 import BeautifulSoup


@dataclasses.dataclass
class Person:
    id: int
    name: str
    aliases: list[str]
    birth_date: str
    location: str | None

    def to_str(self, alias_idx: int = -1) -> str:
        if alias_idx == -1:
            name = self.name
        else:
            name = self.aliases[alias_idx]
        person_str = ",".join(
            [
                self.id,
                name,
                self.birth_date or "-",
                self.location or "-",
                "0" if alias_idx == -1 else "1",
                hashlib.sha1(name.encode()).hexdigest(),
            ]
        )
        return person_str


URL = "https://www.fedsfm.ru/documents/terrorists-catalog-portal-act"


def get_html(client: httpx.Client):
    response = client.get(URL)
    return response.text


def parse_html(raw: str):
    soup = BeautifulSoup(raw, "html.parser")
    russianFL = soup.find(id="russianFL")
    return russianFL


pattern = (
    r"^(?P<id>\d+)\.\s+"  # ID
    r"(?P<name>[^,*(\d]+?)\*?\s*,\s*"  # Имя
    r"(?:\((?P<aliases>[^)]+)\)\s*,\s*)?"  # Алиасы (опционально)
    r"(?:(?P<birth_date>\d{2}\.\d{2}\.\d{4}\s+г\.р\.)\s*)?"  # Дата (опционально)
    r"(?:\s*,\s*(?P<location>.*))?"  # Локация (забирает всё оставшееся)
    r"\s*;$"  # Строго последняя точка с запятой
)


def parse_person(text):
    match = re.search(pattern, text)
    if match:
        data = match.groupdict()

        # Обработка списка алиасов (если они есть)
        if data["aliases"]:
            data["aliases"] = [a.strip() for a in data["aliases"].split(";")]
        else:
            data["aliases"] = []

        if data["birth_date"]:
            data["birth_date"] = (
                data["birth_date"].replace(" г.р.", "").replace(".", "-") or None
            )
        return data
    return None


def process_strings(parsed) -> list[Person]:
    rows = []
    for el in parsed.div.ol:
        text = el.text.strip()
        if not text:
            continue

        res = parse_person(text)
        rows.append(Person(**res))

    return rows


def save_to_csv(persons: list[Person], filename="persons.csv"):
    with open(filename, "w", encoding="utf-8") as f:
        for person in persons:
            f.write(person.to_str() + "\n")

            for alias_idx in range(len(person.aliases)):
                f.write(person.to_str(alias_idx=alias_idx) + "\n")


def main():
    client = httpx.Client(verify=False)
    raw = get_html(client=client)

    parsed = parse_html(raw)
    persons = process_strings(parsed)

    save_to_csv(persons)


if __name__ == "__main__":
    main()
