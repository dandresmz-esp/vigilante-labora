"""Discover municipal notice boards from approved LABORA project lists."""
from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def fold(value):
    return "".join(c for c in unicodedata.normalize("NFKD", value.lower()) if not unicodedata.combining(c))


def approved_promoters(text, years, provinces=("46",)):
    """Return relevant municipal promoters, keeping the project as evidence."""
    source = fold(text)
    starts = list(re.finditer(r"\b(?:fotae|festa|fotav)/20\d{2}/\d+/(?:03|12|46)\b", source))
    found = {}
    for index, match in enumerate(starts):
        project = match.group(0).upper()
        year, province = re.search(r"/(20\d{2})/\d+/(\d{2})$", project).groups()
        if int(year) not in years or province not in provinces:
            continue
        section = source[match.start():starts[index + 1].start() if index + 1 < len(starts) else len(source)]
        codes = set(re.findall(r"\b[a-z]{4}\d{4}\b", section))
        if not any(code.startswith(("agao", "adg", "coml")) or code == "imai0110" for code in codes):
            continue
        promoter = re.search(
            r"\b(?:ajuntament|ayuntamiento|ajyuntamiento)\s+(?:(?:de|del|de la)\s+|d['’]\s*)?([a-z][a-z\s'-]{2,70}?)\s+\d{9}\b",
            section,
        )
        locality = re.search(r"localidad objeto de actuacion grupo especialidades alumnos subv\. maxima\s+([a-z][a-z\s'-]{2,65}?)\s+(?:este proyecto|el proyecto|1\s+[a-z]{4}\d{4})", section)
        if not promoter:
            group = re.search(r"\b(?:mancomunitat|mancomunidad)\s+([a-z][a-z\s'-]{2,60}?)\s+\d{9}\b", section)
            found[project] = {"project": project, "name": " ".join(group.group(1).split()) if group else " ".join(locality.group(1).split()) if locality else None}
            continue
        name = " ".join(promoter.group(1).split()).strip(" -'")
        if locality:
            place = " ".join(locality.group(1).split()).strip(" -'")
            if place.startswith(name) and len(place) > len(name):
                name = place
        found[project] = {"project": project, "name": name}
    return list(found.values())


def board_candidates(name):
    slug = re.sub(r"[^a-z0-9]+", "-", fold(name)).strip("-")
    if not slug or len(slug) > 55:
        return []
    return [
        f"https://{slug}.sedelectronica.es/board",
        f"https://{slug}.sedipualba.es/tablondeanuncios/",
        f"https://{slug}.sede.dival.es/tablondeanuncios/",
    ]


def verified_board(name):
    """Accept only a named board on a known municipal platform."""
    expected = re.sub(r"[^a-z0-9]", "", fold(name))
    for url in board_candidates(name):
        try:
            with urlopen(Request(url, headers={"User-Agent": "VigilanteProgramasEmpleo/0.1"}), timeout=7) as response:
                if response.status != 200 or urlsplit(response.url).hostname != urlsplit(url).hostname:
                    continue
                body = response.read(150000).decode("utf-8", errors="replace")
            heading = re.sub(r"[^a-z0-9]", "", fold(body[:10000]))
            structure = "AdvertisementBoardListPanel" in body if ".sedelectronica.es" in url else "anuncio.aspx?id=" in body
            if expected in heading and structure:
                return url
        except Exception:
            continue
    return None
