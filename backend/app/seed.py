from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Property

PROPERTIES: list[dict[str, str]] = [
    {
        "id": "olympic-paddington",
        "name": "Olympic Hotel Paddington",
        "source_url": "https://www.booking.com/hotel/au/olympic-paddington.html",
    },
    {
        "id": "venus-potts-point-sydney",
        "name": "Potts Point",
        "source_url": "https://www.booking.com/hotel/au/venus-potts-point-sydney.html",
    },
    {
        "id": "venus-surry-hills",
        "name": "Central Sydney",
        "source_url": "https://www.booking.com/hotel/au/venus-surry-hills.html",
    },
    {
        "id": "chateau-de-venus",
        "name": "Darling Harbour",
        "source_url": "https://www.booking.com/hotel/au/chateau-de-venus.html",
    },
]

PROPERTY_IDS = [p["id"] for p in PROPERTIES]


def seed_properties(db: Session) -> int:
    """Insert or update the fixed property list. Returns number of new rows."""
    existing = {p.id: p for p in db.scalars(select(Property))}
    created = 0
    for spec in PROPERTIES:
        row = existing.get(spec["id"])
        if row is None:
            db.add(Property(**spec))
            created += 1
        else:
            row.name = spec["name"]
            row.source_url = spec["source_url"]
    db.commit()
    return created
