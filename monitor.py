"""Vigilancia de fuentes públicas, sin LLM. No presenta solicitudes ni envía sin --deliver."""
from __future__ import annotations

import argparse
import difflib
import hashlib
import html
import io
import json
import os
from pathlib import Path
import re
import smtplib
import ssl
import sys
import time
import shutil
import subprocess
import tempfile
import threading
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.message import EmailMessage
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit, quote, unquote
from urllib.request import Request, urlopen, build_opener, HTTPRedirectHandler
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from zoneinfo import ZoneInfo

from pypdf import PdfReader

AGENT = "VigilanteProgramasEmpleo/0.1 (public job notices; hourly checks)"
MAX_BYTES = 24 * 1024 * 1024
PDF_RENDER_LOCK = threading.Lock()
HOST_LOCK = threading.Lock()
HOST_FAILURES = {}
HOST_NEXT = {}
EXTRACTION_VERSION = 2
ALLOWED_HOSTS = {"labora.gva.es", "www.idea-alzira.com", "idea-alzira.com", "silla.e-oer.com", "silla.sede.dival.es", "sedeelectronica.alzira.es", "aytosagunto.es", "www.aytosagunto.es", "sagunto.portalemp.com", "picanya.portalemp.com", "picanya.org", "www.picanya.org"}
# Observed document storage redirect used by IDEA's own PDF links.
ALLOWED_HOSTS.add("0b6e09b9-fe3a-4f21-b15a-c9ff5db0fc9a.filesusr.com")
ALLOWED_HOSTS.update({"simatdelavalldigna.sede.dival.es","mancomunitatriberabaixa.sedelectronica.es","sede.algemesi.es","ontinyent.sedipualba.es","lafontdelafiguera.sedelectronica.es","betera.sedelectronica.es","benaguasil.sede.dival.es","alfafar.sedelectronica.es","sedavi.sede.dival.es","alcasser.sedelectronica.es","manises.sedipualba.es","www.mislata.es","rafelbunyol.sedelectronica.es","massamagrell.sedelectronica.es","ayora.sedelectronica.es"})
MONTHS = {"enero":1,"gener":1,"febrero":2,"febrer":2,"marzo":3,"marc":3,"abril":4,"mayo":5,"maig":5,"junio":6,"juny":6,"julio":7,"juliol":7,"agosto":8,"agost":8,"septiembre":9,"setembre":9,"octubre":10,"noviembre":11,"novembre":11,"diciembre":12,"desembre":12}

def utcnow():
    return datetime.now(timezone.utc).isoformat()

def fold(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c))

def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)

def canonical(url):
    p = urlsplit(url)
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), quote(unquote(p.path), safe="/;:@+"), p.query, ""))

class Page(HTMLParser):
    """Only visible HTML. Anchor context recovers uninformative 'descarga' labels."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.links = [], []
        self.skip = 0
        self.anchor = None
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.skip += 1
        if self.skip:
            return
        if tag in ("p", "div", "br", "li", "h1", "h2", "h3", "tr"):
            self.parts.append("\n")
        if tag == "a":
            self.anchor = {"href":dict(attrs).get("href", ""), "label":"", "context":" ".join(self.parts)[-550:]}
    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self.skip:
            self.skip -= 1
            return
        if self.skip:
            return
        if tag == "a" and self.anchor:
            self.links.append(self.anchor)
            self.anchor = None
        if tag in ("p", "div", "li", "h1", "h2", "h3", "tr"):
            self.parts.append("\n")
    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)
            if self.anchor is not None:
                self.anchor["label"] += data
    def text(self):
        return "\n".join(" ".join(x.split()) for x in "".join(self.parts).splitlines() if x.strip())

def normalize(text):
    """Remove narrowly identified signature metadata, NEVER arbitrary dates/years."""
    clean = []
    signature = 0
    for raw in unicodedata.normalize("NFKC", html.unescape(text)).splitlines():
        line = " ".join(raw.split())
        f = fold(line)
        if re.match(r"^(csv\s*:|c[oó]digo seguro de verificaci[oó]n\s*:|codi segur de verificaci[oó]\s*:|url de validaci[oó]|url de verificaci[oó])", line, re.I):
            continue
        if re.match(r"^(firmado por|firmat per)$", f):
            signature = 5
            continue
        if re.match(r"^(segell|sello|publicat|publicado|data de public|fecha de public)", f):
            signature = 0
        if signature:
            signature -= 1
            if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?", line):
                signature = 0
                continue
        line = re.sub(r"(?i)(firmado electr[oó]nicamente|signat electr[oò]nicament)(\s+(?:el\s+)?\d{1,2}/\d{1,2}/\d{4}(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?)", r"\1 [fecha firma]", line)
        if re.fullmatch(r"(?i)p[aáà]g(?:ina)?\.?\s*\d+\s*(?:de|/)\s*\d+", line):
            continue
        if line:
            clean.append(line)
    return " ".join(clean)

def extract_pdf(data):
    reader = PdfReader(io.BytesIO(data))
    texts = [(p.extract_text() or "") if '/Contents' in p else '' for p in reader.pages]
    # A partly scanned PDF must not be reported as fully read.
    unread = [i+1 for i,t in enumerate(texts) if len(re.sub(r"\s", "", normalize(t))) < 60]
    if unread:
        engine = shutil.which("tesseract")
        node = os.environ.get('OCR_NODE')
        if not engine and not node:
            raise ValueError("PDF sin texto suficiente en páginas " + str(unread) + "; OCR no disponible")
        import pypdfium2
        with tempfile.TemporaryDirectory() as tmp:
            for number in unread:
                path = Path(tmp)/f"page{number}.png"
                # PDFium is not thread safe; OCR processes may run concurrently.
                with PDF_RENDER_LOCK:
                    doc = pypdfium2.PdfDocument(data)
                    page = doc[number-1]
                    bitmap = page.render(scale=2)
                    rendered = bitmap.to_pil()
                    # Extremely sparse scan dust is not an unreadable document page.
                    blank = sum(rendered.convert('L').histogram()[:220]) <= 50
                    if not blank:rendered.save(path)
                    bitmap.close()
                    page.close()
                    doc.close()
                if blank:
                    texts[number-1]=''
                    continue
                command = [engine,str(path),"stdout","-l","spa+cat","--psm","3"] if engine else [node,str(Path(__file__).with_name('ocr.cjs')),str(path)]
                process = subprocess.run(command,capture_output=True,timeout=120)
                recognized = process.stdout.decode("utf-8",errors="replace")
                if engine and (process.returncode or len(recognized.strip()) < 25):
                    for mode in ('6','11'):
                        process=subprocess.run([engine,str(path),'stdout','-l','spa+cat','--psm',mode],capture_output=True,timeout=120)
                        recognized=process.stdout.decode('utf-8',errors='replace')
                        if not process.returncode and len(recognized.strip())>=25:break
                if process.returncode or len(recognized.strip()) < 25:
                    raise ValueError(f"OCR no fiable en página {number}; revisar documento")
                texts[number-1] = recognized
    if not any(len(normalize(t))>=25 for t in texts):
        raise ValueError('OCR: PDF vacío o sin contenido legible')
    return "\n\f\n".join(texts)

def details(text):
    f = fold(" ".join(text.split()))
    result = {"codes":sorted(set(re.findall(r"\b[A-Z]{4}\d{4}\b", text.upper()))), "deadlines":[], "relative_deadlines":[], "publication_dates":[], "review_required":False}
    for m in re.finditer(r"(?:publicat a tauler[^\d]{0,70}|publicado en[^\d]{0,70})(\d{1,2}/\d{1,2}/\d{4})",f):
        try:
            result["publication_dates"].append(datetime.strptime(m.group(1),"%d/%m/%Y").date().isoformat())
        except ValueError:
            result["review_required"] = True
    # Numeric ranges, as in LABORA calendars. Does not infer a year from the clock.
    for m in re.finditer(r"\b(?:del?\s+)?(\d{1,2}/\d{1,2}/\d{4})\s*(?:al?|hasta|[-–])\s*(\d{1,2}/\d{1,2}/\d{4})", f):
        try:
            a,b = [datetime.strptime(x, "%d/%m/%Y").date().isoformat() for x in m.groups()]
            result["deadlines"].append({"start":a,"end":b,"evidence":m.group(0)})
        except ValueError:
            result["review_required"] = True
    months = "|".join(MONTHS)
    pattern = rf"\bdel?\s+(\d{{1,2}})\s+al?\s+(\d{{1,2}})\s+(?:de\s+)?(?:d[’']\s*)?({months})\s+(?:de\s+)?(\d{{4}})"
    for m in re.finditer(pattern, f):
        try:
            d1,d2,month,year = m.groups()
            a = datetime(int(year), MONTHS[month], int(d1)).date().isoformat()
            b = datetime(int(year), MONTHS[month], int(d2)).date().isoformat()
            result["deadlines"].append({"start":a,"end":b,"evidence":m.group(0)})
        except ValueError:
            result["review_required"] = True
    for m in re.finditer(r"\b(\d+|un|uno|dos|tres)\s+di(?:a|es|as)\s+habil(?:es|s)?\b", f):
        result["relative_deadlines"].append(f[max(0,m.start()-90):m.end()+210])
    # Preserve contradictions instead of inventing a computed closing date.
    if result["relative_deadlines"] or len(result["deadlines"]) > 1:
        result["review_required"] = True
    result["deadline_status"] = "fechas_explicitas" if result["deadlines"] else "revisar_documento"
    return result

def candidates(page, base, entity, depth):
    found = {}
    for link in page.links:
        url = canonical(urljoin(base, link["href"]))
        p = urlsplit(url)
        if p.scheme != "https" or p.hostname not in ALLOWED_HOSTS:
            continue
        label = " ".join(link["label"].split())
        context = " ".join(link["context"].split())
        hay = fold(label + " " + url)
        doc = ".pdf" in p.path.lower() or "/documents/" in p.path
        selected = False
        if entity == "LABORA":
            selected = doc and any(w in hay for w in ("calendari", "fechas-presen", "fecha", "calendario"))
            if not doc:
                selected = "/programes-mixtos-d-ocupacio/" in p.path or "tallers-d-ocupacio-per-a-dones" in p.path
        elif entity == "Alzira":
            selected = doc or any(w in hay for w in ("escolataller", "taller", "inserta", "avalem", "formem", "respirall", "teestime"))
        elif entity == "Silla":
            selected = doc or "/programas-mixtos-de-formacion-empleo/" in p.path
            if "/va/" in p.path:
                selected = False
        elif entity == "Sagunt":
            selected = doc or (p.hostname in ("aytosagunto.es","www.aytosagunto.es") and any(x in p.path for x in ("/administracion/empleo/","/formacion-y-empleo/")))
            selected = selected or (p.hostname == "sagunto.portalemp.com" and "/ofertas.html" in p.path)
        elif entity == "Picanya":
            selected = doc or (p.hostname == "picanya.portalemp.com" and "/ofertas.html" in p.path)
        if selected and url != canonical(base):
            found[url] = {"entity":entity,"url":url,"kind":"pdf" if doc else "page","depth":depth+1,"label":label,"context":context}
    return list(found.values())

class NoRelayRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Redirección del lector no permitida')


def fetch(url, validators=None):
    host = urlsplit(url).hostname
    if host not in ALLOWED_HOSTS:
        raise ValueError("Host fuera de la lista permitida")
    with HOST_LOCK:
        if HOST_FAILURES.get(host,0) >= 3:
            raise RuntimeError("Web temporalmente inaccesible tras varios fallos; lectura pendiente hasta siguiente ejecución")
    last = None
    headers={'User-Agent':AGENT}
    relay = os.environ.get('LABORA_RELAY_URL') if host == 'labora.gva.es' else None
    request_url = url
    opener = urlopen
    if relay:
        endpoint = urlsplit(relay)
        if endpoint.scheme != 'https' or endpoint.hostname != 'vigilante-labora-lector.vigilante-dandresmz-esp.workers.dev' or endpoint.username or endpoint.password or endpoint.port not in (None,443) or endpoint.query or endpoint.fragment:
            raise ValueError('Dirección del lector no permitida')
        token = os.environ.get('LABORA_RELAY_TOKEN')
        if not token:
            raise ValueError('Falta credencial del lector')
        headers.update({'Authorization':'Bearer '+token,'User-Agent':'Mozilla/5.0 (compatible; VigilanteLabora/1.0)'})
        request_url = relay.rstrip('/')+'/?'+urlencode({'url':url})
        opener = build_opener(NoRelayRedirect()).open
    if validators:
        if validators.get('etag'):headers['If-None-Match']=validators['etag']
        if validators.get('last_modified'):headers['If-Modified-Since']=validators['last_modified']
    for attempt in range(2):
        try:
            with HOST_LOCK:
                now=time.monotonic();delay=max(0,HOST_NEXT.get(host,0)-now);HOST_NEXT[host]=now+delay+0.5
            if delay:time.sleep(delay)
            with opener(Request(request_url, headers=headers), timeout=30 if relay else 22) as response:
                if relay and urlsplit(response.headers.get('X-Source-URL','')).hostname != 'labora.gva.es':
                    raise ValueError('Origen del lector no verificado')
                if not relay and urlsplit(response.url).hostname not in ALLOWED_HOSTS:
                    raise ValueError("Redirección fuera de fuentes permitidas")
                data = response.read(MAX_BYTES + 1)
                if len(data) > MAX_BYTES:
                    raise ValueError("Documento demasiado grande: requiere revisión")
                with HOST_LOCK:
                    HOST_FAILURES[host] = 0
                return data, response.headers.get("Content-Type", ""), {'etag':response.headers.get('ETag'),'last_modified':response.headers.get('Last-Modified')}
        except Exception as exc:
            if isinstance(exc,HTTPError) and exc.code==304 and validators:
                return None,'application/pdf',validators
            last = exc
            if attempt == 0:
                time.sleep(1)
    if isinstance(last,(TimeoutError,ConnectionError,URLError)) and (not isinstance(last,HTTPError) or last.code >= 500 or last.code in (403,429)):
        with HOST_LOCK:
            HOST_FAILURES[host] = HOST_FAILURES.get(host,0)+1
    raise RuntimeError(str(last))

def inspect_resource(resource):
    try:
        if resource['kind']=='board':
            from boards import collect
            text,children,evidence=collect(resource)
            normalized=normalize(text)
            return dict(ok=True,resource=resource,text=text,normalized=normalized,hash=digest(normalized),details={'board_evidence':evidence,'deadline_status':'fechas_de_exposicion_no_plazos_de_solicitud'},children=children,kind='board')
        cached = resource.get('_cache',{})
        valid_cache=resource['kind']=='pdf' and cached.get('extraction_version')==EXTRACTION_VERSION and cached.get('byte_hash')
        data, content_type, http_cache = fetch(resource["url"], cached.get('http_cache') if valid_cache else None)
        if data is None:
            return dict(ok=True,resource=resource,text='',hash=cached['hash'],details=cached['details'],children=[],kind='pdf',byte_hash=cached['byte_hash'],extraction_version=EXTRACTION_VERSION,http_cache=http_cache)
        is_pdf = data.startswith(b"%PDF")
        byte_hash = hashlib.sha256(data).hexdigest()
        if is_pdf and cached.get('byte_hash') == byte_hash and cached.get('extraction_version') == EXTRACTION_VERSION:
            return dict(ok=True,resource=resource,text='',hash=cached['hash'],details=cached['details'],children=[],kind='pdf',byte_hash=byte_hash,extraction_version=EXTRACTION_VERSION,http_cache=http_cache)
        if resource["kind"] == "pdf" and not is_pdf:
            raise ValueError("Se esperaba PDF; respuesta HTML o protección de acceso")
        children = []
        if is_pdf:
            text = extract_pdf(data)
        elif resource["kind"] == "api":
            payload=json.loads(data.decode("utf-8"))
            items=payload.get("items",[]) if isinstance(payload,dict) else []
            words=("ocupacio","ocupación","empleo","taller","formacio","formación","docent","fotae","escola")
            selected=[x for x in items if any(w in fold(json.dumps(x,ensure_ascii=False)) for w in words)]
            text=json.dumps(selected,ensure_ascii=False,sort_keys=True)
            children=[]
            for match in re.findall(r'https://[^\s"<>\\]+',text):
                docurl=canonical(match.rstrip(').,;'))
                if urlsplit(docurl).hostname in ALLOWED_HOSTS and ('.pdf' in urlsplit(docurl).path.lower() or '/documents/' in urlsplit(docurl).path):
                    children.append(dict(entity=resource['entity'],url=docurl,kind='pdf',depth=resource.get('depth',0)+1,label='Documento enlazado'))
        else:
            page = Page()
            page.feed(data.decode("utf-8", errors="replace"))
            text = page.text()
            if resource["kind"] == "snapshot":
                if len(text) < 100 or not any(k in fold(text) for k in ("tablon","anuncio","edicto","ocupacio","empleo")):
                    raise ValueError("Tablón vacío o estructura no reconocida")
                normalized=normalize(text)
                return {"ok":True,"resource":resource,"text":text,"normalized":normalized,"hash":digest(normalized),"details":details(text),"children":[],"kind":"snapshot","byte_hash":byte_hash,"extraction_version":EXTRACTION_VERSION,"http_cache":http_cache}
            if len(text) < 200 or not any(k in fold(text) for k in ("taller", "ocupacio", "empleo", "formacio", "labora", "anuncio", "edicto")):
                raise ValueError("Contenido no reconocido, vacío o página de error")
            children = candidates(page, resource["url"], resource["entity"], resource.get("depth",0))
            if resource['kind']=='notice':
                for link in page.links:
                    docurl=canonical(urljoin(resource['url'],link['href']))
                    if urlsplit(docurl).hostname in ALLOWED_HOSTS and any(w in docurl.lower() for w in ('.pdf','documentoinformativo.aspx','documento.aspx','download')):
                        children.append(dict(entity=resource['entity'],url=docurl,kind='pdf',depth=resource.get('depth',0)+1,label=link['label']))
            if not children and resource['kind']!='notice':
                raise ValueError("No se localizaron enlaces de programas/documentos; revisar estructura")
            # Include link identities: new calendars are detected even if text is unchanged.
            text += "\n" + "\n".join(sorted(x["url"] for x in children))
        normalized = normalize(text)
        return {"ok":True,"resource":resource,"text":text,"normalized":normalized,"hash":digest(normalized),"details":details(text),"children":children,"kind":"pdf" if is_pdf else resource['kind'],"byte_hash":byte_hash,"extraction_version":EXTRACTION_VERSION,"http_cache":http_cache}
    except Exception as exc:
        return {"ok":False,"resource":resource,"error":str(exc)[:350]}

def transition(old, result, now):
    r = result["resource"]
    record = dict(old or {})
    record.update({k:v for k,v in r.items() if k != "context" and not k.startswith('_')})
    record["last_attempt"] = now
    if not result["ok"]:
        record.update(status="fallando",error=result["error"])
        event = None
        if not old or old.get("status") != "fallando":
            event = {"type":"fallo_fuente","entity":r["entity"],"url":r["url"],"message":result["error"]}
        return record,event
    record.update(status="verificada",last_success=now,hash=result["hash"],details=result["details"],kind=result["kind"])
    record["children"] = [canonical(x["url"]) for x in result.get("children", [])]
    for key in ('byte_hash','extraction_version','http_cache'):
        if key in result:record[key]=result[key]
    record.pop("error",None)
    changed = old and old.get("hash") != result["hash"]
    recovered = old and old.get("status") == "fallando"
    typ = "contenido_modificado" if changed else "fuente_recuperada" if recovered else "fuente_nueva" if not old else None
    event = None
    if typ:
        event = {"type":typ,"entity":r["entity"],"url":r["url"],"label":r.get("label",""),"details":result["details"],"previous_details":(old or {}).get("details"),"message":"Revisar documento: no se presupone que sea una convocatoria abierta."}
    return record,event

def event_id(event):
    return digest(json.dumps(event, sort_keys=True, ensure_ascii=False))

def mail_body(events, report):
    lines = ["VIGILANTE DE TALLERES — LABORA Y MUNICIPIOS", "Comprobación: " + report["finished"],
             "Los avisos son cambios detectados, no una confirmación de que puedas acceder al puesto.", ""]
    for event in events:
        lines += [event["type"] + " — " + event.get("entity", ""),event.get("label", ""),event.get("url", ""),event.get("message", "")]
        info = event.get("details", {})
        for deadline in info.get("deadlines", []):
            lines.append("Fechas del documento: " + deadline["start"] + " a " + deadline["end"])
        for relative in info.get("relative_deadlines", [])[:4]:
            lines.append("Plazo relativo (revisar publicación): " + relative)
        if info and not info.get("deadlines"):
            lines.append("Plazo: consultar el documento; no identificado con seguridad.")
        lines.append("")
    lines.append("Cobertura: " + json.dumps(report["coverage"], ensure_ascii=False))
    return "\n".join(lines)

def send_mail(subject, body):
    names = ["SMTP_HOST","SMTP_USER","SMTP_PASSWORD","ALERT_FROM","ALERT_TO"]
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        raise RuntimeError("Falta configurar " + ", ".join(missing))
    msg = EmailMessage()
    msg["Subject"],msg["From"],msg["To"] = subject,os.environ["ALERT_FROM"],os.environ["ALERT_TO"]
    msg.set_content(body)
    port = int(os.environ.get("SMTP_PORT", "465"))
    with smtplib.SMTP_SSL(os.environ["SMTP_HOST"], port, context=ssl.create_default_context(), timeout=30) as smtp:
        smtp.login(os.environ["SMTP_USER"],os.environ["SMTP_PASSWORD"])
        smtp.send_message(msg)

def scheduled_now(now):
    local = now.astimezone(ZoneInfo("Europe/Madrid"))
    return (local.weekday() < 5 and (8 <= local.hour <= 20 or local.hour in (6,22))) or (local.weekday() >= 5 and local.hour == 9)

def run(config, state_path, runtime, deliver=False, initialize=False):
    with HOST_LOCK:
        HOST_FAILURES.clear()
        HOST_NEXT.clear()
    state_path,runtime = Path(state_path),Path(runtime)
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {"version":1,"resources":{},"pending":{},"gaps_reported":[]}
    if initialize:
        # An explicit baseline starts clean and never carries historical alerts.
        state = {"version":1,"resources":{},"pending":{},"gaps_reported":[]}
    original_resources=dict(state['resources'])
    bootstrap = not original_resources
    runtime.mkdir(parents=True, exist_ok=True)
    state['in_progress']={'started':utcnow(),'checked':0}
    write_json(state_path,state)
    queue = {canonical(r["url"]):dict(r,depth=0) for r in config["sources"]}
    # Discover new material before spending the budget on detached historical links.
    historical = {u:{k:r[k] for k in ("url","entity","kind","depth","label") if k in r} for u,r in state['resources'].items()}
    seen,results = set(),[]
    limit = config.get("max_resources",220)
    overflow = False
    with ThreadPoolExecutor(max_workers=4) as pool:
        while queue:
            batch = [v for u,v in queue.items() if u not in seen]
            queue = {}
            if not batch:
                break
            print(f"Comprobando lote de {len(batch)} recursos; {len(seen)} revisados",flush=True)
            for r in batch:
                old=state['resources'].get(canonical(r['url']),{})
                if old.get('status')=='verificada':
                    r['_cache']={k:old[k] for k in ('byte_hash','extraction_version','hash','details','http_cache') if k in old}
            remaining = limit-len(seen)
            if len(batch) > remaining:
                overflow = True
                batch = batch[:max(0,remaining)]
            if not batch:
                break
            for result in pool.map(inspect_resource,batch):
                u = canonical(result["resource"]["url"])
                seen.add(u)
                results.append(result)
                record,event=transition(original_resources.get(u),result,utcnow())
                state['resources'][u]=record
                if event and not (initialize and bootstrap and event['type']=='fuente_nueva'):
                    event['version']=record.get('hash',result.get('error',''))
                    for key,older in list(state['pending'].items()):
                        if older.get('url')==event.get('url'):state['pending'].pop(key)
                    state['pending'][event_id(event)]=event
                state['in_progress']['checked']=len(results)
                if len(results)==1 or len(results)%10==0:write_json(state_path,state)
                if result["ok"]:
                    previous_children=set((original_resources.get(u) or {}).get('children',[]))
                    for child in result["children"]:
                        # On the first pass, page hashes inventory every historical link.
                        # Later passes fully read only newly discovered PDFs, while pages
                        # remain traversed so a new link is noticed immediately.
                        read_child = child["kind"] != "pdf" and child["depth"] <= config.get("max_depth",2)
                        if child["kind"] == "pdf" and not bootstrap and canonical(child["url"]) not in previous_children:
                            read_child = True
                        if read_child:
                            if child["url"] not in seen:
                                queue[child["url"]] = child
            if not queue and historical:
                queue={u:r for u,r in historical.items() if u not in seen}
                historical={}
    now,events = utcnow(),[]
    for result in results:
        u = canonical(result["resource"]["url"])
        record,event = transition(original_resources.get(u),result,now)
        state["resources"][u] = record
        if event and not (initialize and bootstrap and event['type']=='fuente_nueva'):
            # Couple event identity to version; delivery failures remain pending.
            event["version"] = record.get("hash",result.get("error",""))
            events.append(event)
        if result["ok"] and result['text']:
            (runtime / (digest(u)+".txt")).write_text(result["text"],encoding="utf-8")
    for gap in config.get("coverage_gaps",[]):
        key = event_id(gap)
        if key not in state["gaps_reported"]:
            events.append({"type":"cobertura_incompleta","entity":gap["entity"],"url":gap["url"],"message":gap["reason"]})
            state["gaps_reported"].append(key)
    if overflow:
        events.append({"type":"limite_alcanzado","message":"Se alcanzó el límite de recursos; cobertura incompleta. No es una ejecución íntegra."})
    for event in events:
        event['detected_at']=now
        if event.get('url'):
            for key,older in list(state['pending'].items()):
                if older.get('url')==event['url']:state['pending'].pop(key)
        state["pending"][event_id(event)] = event
    coverage = {}
    for entity in sorted({s["entity"] for s in config["sources"]}):
        rr = [r for r in state["resources"].values() if r["entity"] == entity]
        failures = sum(r["status"] == "fallando" for r in rr)
        gaps = sum(g["entity"] == entity for g in config.get("coverage_gaps",[]))
        coverage[entity] = {"status":"parcial" if failures or gaps or overflow else "lectura_verificada", "resources":len(rr),"failures":failures,"unvalidated_sources":gaps}
    report = {"finished":now,"checked":len(results),"new_events":len(events),"pending_events":len(state["pending"]),"overflow":overflow,"coverage":coverage,"delivery":"no_solicitada","external_watchdog":"no_configurado"}
    preview = mail_body(list(state["pending"].values()),report)
    (runtime/"aviso_preparado.txt").write_text(preview,encoding="utf-8")
    write_json(state_path,state) # persist outbox before trying SMTP
    failure = any(not r["ok"] for r in results) or overflow
    if deliver:
        try:
            if state["pending"]:
                # One digest per pass, including the initial historical baseline.
                entries = list(state["pending"].items())
                send_mail("Vigilante: novedades o incidencias de talleres",mail_body([v for k,v in entries],report))
                state['pending'].clear()
                write_json(state_path,state)
                report["delivery"] = "aceptada_por_SMTP_pendiente_confirmar_recepcion"
            else:
                report["delivery"] = "sin_novedades"
            # Heartbeat certifies execution, not full source coverage; independent service must alert on silence.
            ping = os.environ.get("HEARTBEAT_URL")
            if os.environ.get('HEARTBEAT_DEFERRED')=='1':
                report['external_watchdog']='pendiente_de_persistir_estado'
            elif ping:
                if urlsplit(ping).scheme != "https":
                    raise RuntimeError("HEARTBEAT_URL debe usar HTTPS")
                with urlopen(Request(ping,method="POST",data=b"completed"),timeout=15) as response:
                    response.read(100)
                report["external_watchdog"] = "senal_enviada"
            else:
                failure = True
        except Exception as exc:
            report["delivery"] = "fallo: " + type(exc).__name__ # do not expose secrets in logs
            failure = True
    state["last_execution"] = now
    state.pop('in_progress',None)
    report['pending_events']=len(state['pending'])
    write_json(state_path,state)
    write_json(runtime/"informe.json",report)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 2 if failure else 0

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config",default="sources.json")
    parser.add_argument("--state",default="runtime/state.json")
    parser.add_argument("--runtime",default="runtime")
    parser.add_argument("--deliver",action="store_true",help="Enviar únicamente después de configurar y autorizar el canal")
    parser.add_argument("--scheduled",action="store_true")
    parser.add_argument("--initialize",action="store_true",help="Crear la base inicial sin avisar por documentos históricos")
    args = parser.parse_args()
    if args.scheduled and not scheduled_now(datetime.now(timezone.utc)):
        print("Fuera de franja; no se comprueban fuentes. El flujo de GitHub comprueba por separado la señal de vida.")
        return 0
    return run(json.loads(Path(args.config).read_text(encoding="utf-8")),args.state,args.runtime,args.deliver,args.initialize)

if __name__ == "__main__":
    sys.exit(main())
