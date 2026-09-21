"""Read-only navigation of public municipal boards, including pagination."""
import re
import html
from html.parser import HTMLParser
from urllib.parse import urlencode,urljoin
from urllib.request import build_opener,HTTPCookieProcessor,Request
from http.cookiejar import CookieJar

class Form(HTMLParser):
 def __init__(self):super().__init__();self.fields={};self.select=None;self.first=True
 def handle_starttag(self,t,attrs):
  a=dict(attrs)
  if t=='input' and a.get('name') and a.get('type','').lower() in ('hidden','text'):
   self.fields[a['name']]=a.get('value','')
  if t=='select':self.select=a.get('name');self.first=True
  if t=='option' and self.select:
   if self.first or 'selected' in a:self.fields[self.select]=a.get('value','')
   self.first=False
 def handle_endtag(self,t):
  if t=='select':self.select=None

def collect(resource):
 from monitor import Page,fold
 opener=build_opener(HTTPCookieProcessor(CookieJar()))
 def get(url,fields=None):
  req=Request(url,data=urlencode(fields).encode() if fields is not None else None,headers={'User-Agent':'VigilanteProgramasEmpleo/0.1'})
  with opener.open(req,timeout=25) as r:
   b=r.read(4000000);charset=r.headers.get_content_charset() or 'utf-8'
  return b.decode(charset,errors='replace')
 url=resource['url'];first=get(url);pages=[first];children=[]
 host=__import__('urllib.parse',fromlist=['urlsplit']).urlsplit(url).hostname or ''
 if host.endswith('.sedelectronica.es'):
  if 'AdvertisementBoardListPanel' not in first:raise ValueError('Tablón electrónico: estructura no reconocida')
  parts=[];ids=set()
  for row in re.findall(r'<tr\b.*?</tr>',first,re.S|re.I):
   found=re.search(r'href="([^"]*/preview-document/([^"]+))"',row,re.I)
   if not found:continue
   detail=urljoin(url,html.unescape(found[1]));ids.add(found[2]);p=Page();p.feed(row);label=p.text();parts.append(label)
   # Preserve the stable row as its own resource. The preview wrapper contains
   # volatile session data, so it must not be downloaded or hashed.
   hay=fold(label)
   staff=any(w in hay for w in ('docent','formador','monitor','director','personal','auxiliar administrativ','orientador','coordinador'))
   opportunity=any(w in hay for w in ('convoc','seleccio','seleccion','vacant','vacante','borsa','bolsa','substituc','sustituc','renuncia','bases','plazo','termini'))
   program=any(w in hay for w in ('taller de empleo','taller d ocupacio','tallers d ocupacio','escuela taller','escola taller','programa mixt','fotae','festa','fetf','formem','avalem','labora'))
   if opportunity and (staff or program):
    children.append({'entity':resource['entity'],'url':detail,'kind':'listing_notice','depth':1,'label':label[:350]})
  # The preview page contains volatile session data. The stable board row already
  # includes document identity, description and publication date, so comparing
  # the full listing detects additions without false changes from the wrapper.
  return '\n'.join(parts),children,{'pages':1,'announcements':len(ids),'validation':'server_listing_read'}
 if resource['entity']=='Alzira':
  total_match=re.search(r'var TOTAL_LENGTH\s*=\s*(\d+)',first)
  size_match=re.search(r'var PAGINATION\s*=\s*(\d+)',first)
  if not total_match or not size_match:raise ValueError('Alzira: estructura del tablón no reconocida')
  total,size=int(total_match[1]),int(size_match[1])
  if not size or total>500:raise ValueError('Alzira: paginación fuera del límite')
  for start in range(size,total,size):
   pages.append(get(url.split('?')[0]+'?'+urlencode({'formAction':'btBuscarEdictos','listado':'VIGENTES','st':str(start)})))
  ids=set();parts=[]
  for source in pages:
   ids.update(re.findall(r'id="edicto_(\d+)"',source))
   # Cards are the only data, excluding filters and navigation.
   for match in re.finditer(r'<div[^>]+id="edicto_(\d+)"',source):
    segment=source[match.start():]
    segment=segment[:segment.find('Publicado:')+80]
    p=Page();p.feed(segment);parts.append(p.text())
    detail=url.split('?')[0]+'?'+urlencode({'formAction':'btMostrarDetalle','idedicto':match[1]})
    if any(w in fold(p.text()) for w in ('docent','taller','formacio','empleo','ocupacio','labora','respirall')):
     children.append({'entity':'Alzira','url':detail,'kind':'notice','depth':1,'label':p.text()[:180]})
  if len(ids)!=total:raise ValueError(f'Alzira: esperados {total} anuncios; leídos {len(ids)}. Paginación incompleta')
 else:
  count_matches=re.findall(r'P(?:á|&#225;)gina\s+\d+\s+de\s+(\d+)',first)
  count=max(map(int,count_matches)) if count_matches else 1
  entity=resource['entity']
  if count>20:raise ValueError(f'{entity}: más de 20 páginas, revisar límite')
  page_field='ctl00$ctl00$cphM$cph$ddlPaginaAnuncios'
  current=first
  for n in range(1,count):
   form=Form();form.feed(current)
   if page_field not in form.fields:raise ValueError(f'{entity}: selector de página ausente')
   form.fields[page_field]=str(n);form.fields['__EVENTTARGET']=page_field;form.fields['__EVENTARGUMENT']=''
   current=get(url,form.fields);pages.append(current)
  parts=[];ids=set();signatures=set()
  for source in pages:
   page_ids=set(re.findall(r'anuncio\.aspx\?id=(\d+)',source))
   if not page_ids:raise ValueError(f'{entity}: listado vacío o ilegible; requiere comprobación')
   signature=tuple(sorted(page_ids))
   if signature in signatures:raise ValueError(f'{entity}: la paginación devuelve anuncios repetidos')
   signatures.add(signature);ids.update(page_ids)
   # All announcement titles/dates are compared, regardless of applicant profile.
   for row in re.findall(r'<tr\b.*?</tr>',source,re.S|re.I):
    found=re.search(r'anuncio\.aspx\?id=(\d+)',row)
    if not found:continue
    p=Page();p.feed(row);parts.append(p.text())
    if any(w in fold(p.text()) for w in ('docent','taller','formacio','empleo','ocupacio','labora','avanca')):
     children.append({'entity':entity,'url':urljoin(url,'anuncio.aspx?id='+found[1]),'kind':'notice','depth':1,'label':p.text()[:180]})
  total=len(ids)
 return '\n'.join(parts),children,{'pages':len(pages),'announcements':total,'validation':'all_listing_pages_read'}
