"""Turn official approved-project lists and notices into a readable register."""
from __future__ import annotations

from datetime import date, datetime
import csv
import io
import re
import unicodedata
from zoneinfo import ZoneInfo

PROJECT = re.compile(r"\b(?:FOTAE|FESTA|FOTAV)/20\d{2}/\d+/(?:03|12|46)\b", re.I)
SPECIALTY = re.compile(r"(?m)^\s*\d+\s+([A-Z]{4}\d{4})\s+([^\n]{3,110})", re.I)
PROFILE_PREFIXES = ("AGAO", "ADG", "COML")
REGISTER_URL = "https://github.com/dandresmz-esp/vigilante-labora/blob/estado-vigilante/registro.md"
CATALOG_URL = "https://github.com/dandresmz-esp/vigilante-labora/blob/estado-vigilante/catalogo.md"
PLAZAS_CSV_URL = "https://github.com/dandresmz-esp/vigilante-labora/raw/refs/heads/estado-vigilante/plazas.csv"
CATALOG_CSV_URL = "https://github.com/dandresmz-esp/vigilante-labora/raw/refs/heads/estado-vigilante/catalogo.csv"


def fold(value):
    return "".join(c for c in unicodedata.normalize("NFKD", value.lower()) if not unicodedata.combining(c))


def approved_projects(text, source_url, years):
    """Extract one row per approved project without treating its period as an application window."""
    matches = list(PROJECT.finditer(text))
    rows = []
    for index, match in enumerate(matches):
        code = match.group().upper()
        year = int(code.split("/")[1])
        if year not in years:
            continue
        section = text[match.end():matches[index + 1].start() if index + 1 < len(matches) else len(text)]
        header = section[:900]
        if "aprobator" not in fold(header) and "aprobado" not in fold(header):
            continue
        promoter = re.search(r"\b(AJUNTAMENT|AYUNTAMIENTO|AJYUNTAMIENTO|MANCOMUNITAT|MANCOMUNIDAD)\s+(.{3,110}?)\s+(\d{9})\b", header, re.I | re.S)
        if promoter:
            name = " ".join(promoter.group(2).split()).strip(" -")
            entity = promoter.group(1).title().replace("Ajyuntamiento", "Ayuntamiento") + " " + name.title()
        else:
            locality = re.search(r"LOCALIDAD OBJETO DE ACTUACI.N GRUPO ESPECIALIDADES ALUMNOS SUBV\. M.XIMA\s+([^\n]+)", section, re.I)
            place = " ".join(locality.group(1).split()).title() if locality else ""
            if not any(char.isalpha() for char in place):
                place = ""
            entity = "Entidad por verificar" + (" (" + place + ")" if place else "")
        period = re.search(r"\b(\d{2}/\d{2}/\d{2,4})\s*[-–]\s*(\d{2}/\d{2}/\d{2,4})\b", header)
        period_text = " – ".join(period.groups()) if period else "No indicado"
        suspicious_period = bool(period and abs(int(period.group(2).split("/")[-1]) - int(period.group(1).split("/")[-1])) > 2)
        if suspicious_period:
            period_text = "Por verificar en PDF (" + period_text + ")"
        specialties = []
        for specialty in SPECIALTY.finditer(section):
            specialty_code = specialty.group(1).upper()
            description = " ".join(specialty.group(2).split()).rstrip(" 0123456789")
            if specialty_code not in {item["code"] for item in specialties}:
                specialties.append({"code": specialty_code, "name": description})
        category = code.split("/")[0]
        rows.append({
            "id": code, "type": category, "year": year,
            "province": {"03":"Alicante","12":"Castellón","46":"Valencia"}[code.split("/")[-1]],
            "entity": entity, "specialties": specialties,
            "profile_match": any(item["code"].startswith(PROFILE_PREFIXES) or item["code"] == "IMAI0110" for item in specialties) if specialties else None,
            "project_period": period_text,
            "application_deadline": "No publicado en este listado",
            "status": "Proyecto aprobado; datos por verificar" if not specialties or entity.startswith("Entidad por verificar") or suspicious_period else "Proyecto aprobado; selección por seguir",
            "source_url": source_url,
        })
    return rows


def opportunity(event):
    if event.get("category") not in ("accion", "revisar"):
        return None
    deadlines = event.get("active_deadlines") or event.get("details", {}).get("deadlines") or []
    deadline = "; ".join(item["start"] + " a " + item["end"] for item in deadlines)
    if not deadline:
        deadline = "Plazo por confirmar en el anuncio"
    match = PROJECT.search(" ".join((event.get("label", ""), event.get("excerpt", ""))))
    return {"url":event.get("url", ""),"project_id":match.group().upper() if match else "Sin vinculación confirmada",
            "entity":event.get("entity", ""),"title":event.get("label", "") or "Anuncio oficial",
            "deadline":deadline,"deadline_end":max((item["end"] for item in deadlines),default=""),
            "detected_at":event.get("detected_at", ""),"status":event["category"]}


def escape(value):
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def render_catalogue(projects, opportunities, checked_at):
    local_time = datetime.fromisoformat(checked_at).astimezone(ZoneInfo("Europe/Madrid"))
    current_year = local_time.year
    rows = [p for p in projects.values() if p["year"] in (current_year, current_year + 1)]
    rows.sort(key=lambda p:(p["profile_match"] is not True,p["province"],p["entity"],p["id"]))
    matched = sum(p["profile_match"] is True for p in rows)
    incomplete = sum(p["status"].endswith("verificar") for p in rows)
    linked = {}
    for notice in opportunities.values():
        project_id = notice.get("project_id", "")
        if project_id in projects and (project_id not in linked or notice.get("detected_at", "") > linked[project_id].get("detected_at", "")):
            linked[project_id] = notice
    lines = ["# Registro de talleres y convocatorias", "",
             "Actualizado: " + local_time.strftime("%d/%m/%Y %H:%M") + " (hora peninsular). Fuente: documentos oficiales revisados por el vigilante.", "",
             f"Proyectos aprobados: **{len(rows)}**. Con especialidades afines al perfil: **{matched}**.", "",
             f"Fichas con datos por verificar en el PDF: **{incomplete}**.", "",
             "El período previsto del proyecto **no es** el plazo para solicitar una plaza. Los plazos de selección aparecen solo en la sección de convocatorias.", "",
             "El catálogo incluye Alicante, Castellón y Valencia. El seguimiento de tablones municipales está configurado actualmente para la provincia de Valencia.", "",
             "## Proyectos aprobados", "",
             "| Expediente | Tipo | Provincia | Entidad promotora | Especialidades a impartir | Período previsto | Plazo de solicitud | Perfil | Fuente | Anuncio de personal |", 
             "|---|---|---|---|---|---|---|---|---|---|"]
    for p in rows:
        specialties = "; ".join(item["code"] + " " + item["name"] for item in p["specialties"]) or "Por verificar en el PDF"
        notice = linked.get(p["id"])
        deadline = notice["deadline"] if notice else p["application_deadline"]
        fields = [p["id"],p["type"],p["province"],p["entity"],specialties,p["project_period"],deadline,"Sí" if p["profile_match"] is True else "No" if p["profile_match"] is False else "Por verificar","[LABORA]("+p["source_url"]+")","[Abrir]("+notice["url"]+")" if notice else "—"]
        lines.append("| " + " | ".join(escape(x) for x in fields) + " |")
    lines += ["", "## Convocatorias y plazos detectados", "",
              "Una convocatoria solo se vincula a un expediente cuando el anuncio indica su código.", "",
              "| Detectada | Entidad | Anuncio | Expediente vinculado | Plazo de solicitud | Estado | Fuente |",
              "|---|---|---|---|---|---|---|"]
    entries=sorted(opportunities.values(),key=lambda item:item["detected_at"],reverse=True)
    if not entries:
        lines.append("| — | — | No hay convocatorias nuevas pendientes de revisar | — | — | — | — |")
    for item in entries[:100]:
        status = "Plazo finalizado" if item.get("deadline_end") and item["deadline_end"] < local_time.date().isoformat() else item["status"]
        if not item.get("deadline_end") and item.get("detected_at", "")[:10] < date.fromordinal(local_time.date().toordinal() - 30).isoformat():
            status = "Antiguo; vigencia por verificar"
        fields=[item["detected_at"][:10],item["entity"],item["title"],item["project_id"],item["deadline"],status,"[Anuncio oficial]("+item["url"]+")"]
        lines.append("| " + " | ".join(escape(x) for x in fields) + " |")
    lines.append("")
    return "\n".join(lines)


def render_register(projects, opportunities, checked_at, coverage=None):
    """Action page: show application windows before background project data."""
    local_time = datetime.fromisoformat(checked_at).astimezone(ZoneInfo("Europe/Madrid"))
    today = local_time.date().isoformat()
    live, review, future = [], [], []
    for item in opportunities.values():
        end = item.get("deadline_end", "")
        if end and end < today:
            continue
        deadline = item.get("deadline", "")
        intervals = re.findall(r"(20\d{2}-\d{2}-\d{2}) a (20\d{2}-\d{2}-\d{2})", deadline)
        if any(start <= today <= finish for start, finish in intervals):
            live.append(item)
        elif intervals and all(start > today for start, _ in intervals):
            future.append(item)
        elif item.get("detected_at", "")[:10] >= date.fromordinal(local_time.date().toordinal() - 30).isoformat():
            review.append(item)
    lines = ["# Plazas de talleres: qué hacer hoy", "",
             "Última comprobación: " + local_time.strftime("%d/%m/%Y %H:%M") + " (hora peninsular).", "",
             "**El aviso para presentar la solicitud llega por correo cuando se detecta una convocatoria con plazo abierto.** Comprueba siempre el anuncio oficial antes de enviarla.", "",
             "## Plazo abierto: presenta la solicitud", ""]
    incomplete = [name for name, result in (coverage or {}).items() if result.get("status") != "lectura_verificada"]
    if incomplete:
        lines[4:4] = ["**Vigilancia incompleta en: " + escape(", ".join(incomplete)) + ".** Puede haber anuncios aún no detectados.", ""]
    def add_items(items):
        for item in sorted(items, key=lambda row: (row.get("deadline_end") or "9999", row.get("entity", ""))):
            lines.extend(["- **" + escape(item.get("entity", "Entidad")) + "** — " + escape(item.get("title", "Anuncio de personal")),
                          "  - Plazo: " + escape(item.get("deadline", "Por confirmar en el anuncio")),
                          "  - [Abrir el anuncio oficial](" + item["url"] + ")", ""])
    if live:
        add_items(live)
    else:
        lines.extend(["No hay convocatorias con plazo abierto confirmado en las fuentes vigiladas.", ""])
    lines.extend(["## Revisar hoy: plazo sin confirmar", ""])
    if review:
        add_items(review)
    else:
        lines.extend(["No hay anuncios recientes pendientes de confirmar.", ""])
    lines.extend(["## Próximas aperturas conocidas", ""])
    if future:
        add_items(future)
    else:
        lines.extend(["No hay aperturas futuras confirmadas.", ""])
    lines.extend(["[Descargar convocatorias para Excel](" + PLAZAS_CSV_URL + ") · [Descargar proyectos aprobados para Excel](" + CATALOG_CSV_URL + ")", "",
                  "[Ver proyectos aprobados para seguimiento](" + CATALOG_URL + "). Su aprobación todavía no permite solicitar una plaza.", ""])
    return "\n".join(lines)


def render_csv(projects, opportunities, checked_at, kind):
    """Semicolon CSV with UTF-8 BOM for direct opening in Spanish Excel."""
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    if kind == "plazas":
        writer.writerow(["Entidad", "Anuncio", "Expediente", "Plazo", "Estado", "Enlace oficial"])
        today = datetime.fromisoformat(checked_at).astimezone(ZoneInfo("Europe/Madrid")).date().isoformat()
        for item in sorted(opportunities.values(), key=lambda row: row.get("deadline_end") or "9999"):
            if item.get("deadline_end") and item["deadline_end"] < today:
                continue
            writer.writerow([item.get("entity", ""), item.get("title", ""), item.get("project_id", ""),
                             item.get("deadline", ""), item.get("status", ""), item.get("url", "")])
    elif kind == "catalogo":
        writer.writerow(["Expediente", "Tipo", "Provincia", "Entidad promotora", "Especialidades", "Período previsto del proyecto", "Plazo de solicitud", "Perfil afín", "Fuente oficial"])
        for item in sorted(projects.values(), key=lambda row: (row.get("province", ""), row.get("entity", ""), row.get("id", ""))):
            writer.writerow([item.get("id", ""), item.get("type", ""), item.get("province", ""), item.get("entity", ""),
                             "; ".join(x["code"] + " " + x["name"] for x in item.get("specialties", [])),
                             item.get("project_period", ""), item.get("application_deadline", ""),
                             "Sí" if item.get("profile_match") is True else "No" if item.get("profile_match") is False else "Por verificar",
                             item.get("source_url", "")])
    else:
        raise ValueError("Tipo de CSV desconocido")
    return "\ufeff" + output.getvalue()
