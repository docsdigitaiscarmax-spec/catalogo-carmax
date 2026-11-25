"""Lê o estoque de carmaxsantos.com.br e gera docs/estoque.json.

Roda sozinho no GitHub Actions (ver .github/workflows/atualizar.yml).
Só usa a biblioteca padrão do Python.
"""
import html
import json
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from pathlib import Path

# cada loja tem endereços alternativos: usa o primeiro que responder
LOJAS = [
    ("carmax", ["https://carmax.com.br", "https://carmaxsantos.com.br", "https://www.carmax.com.br"]),
    ("outlet", ["https://www.outletcarmax.com.br", "https://outletcarmax.com.br"]),
]


def escolher_base(bases):
    for b in bases:
        try:
            h = baixar(b + "/estoque", tentativas=2)
            if "/veiculo/" in h:
                print(f"usando {b}")
                return b
        except Exception as e:  # noqa: BLE001
            print(f"  {b} fora do ar: {e}", file=sys.stderr)
    return None
UA = {"User-Agent": "Mozilla/5.0 (catalogo-carmax; +https://github.com)"}
SAIDA = Path(__file__).parent / "docs" / "estoque.json"


def baixar(url, tentativas=3):
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            if i == tentativas - 1:
                raise
            print(f"  erro em {url}: {e}; tentando de novo", file=sys.stderr)
            time.sleep(3 * (i + 1))


def texto(s):
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def numero(s):
    d = re.sub(r"[^\d]", "", s or "")
    return int(d) if d else 0


def ler_listagem(loja, BASE):
    carros, vistos = [], set()
    for pagina in range(1, 40):
        url = f"{BASE}/estoque" + (f"?page={pagina}" if pagina > 1 else "")
        h = baixar(url)
        artigos = re.findall(r"<article\b.*?</article>", h, re.S | re.I)
        novos = 0
        for art in artigos:
            m = re.search(r'href="(https?://[^"]+/veiculo/[^"?#]+)', art)
            if not m or m.group(1) in vistos:
                continue
            link = m.group(1)
            vistos.add(link)
            novos += 1
            nome = texto((re.search(r"<h5[^>]*>(.*?)</h5>", art, re.S) or [None, ""])[1])
            ps = [texto(p) for p in re.findall(r"<p[^>]*>(.*?)</p>", art, re.S)]
            campos = {}
            for i in range(0, len(ps) - 1):
                if ps[i] in ("Ano", "Km", "Cor", "Combustível", "Câmbio"):
                    campos[ps[i]] = ps[i + 1]
            preco = next((p for p in ps if p.startswith("R$")), "")
            capa = re.search(r'<img[^>]+src="([^"]+)"', art)
            carros.append({
                "loja": loja,
                "id": link.rsplit("/", 1)[1].split("-")[0],
                "link": link,
                "nome": nome,
                "ano": campos.get("Ano", "").replace(" ", ""),
                "km": numero(campos.get("Km")),
                "cor": campos.get("Cor", ""),
                "combustivel": campos.get("Combustível", ""),
                "preco": numero(preco) // 100 if "," in preco else numero(preco),
                "capa": capa.group(1) if capa else "",
            })
        print(f"{loja} página {pagina}: {novos} carros")
        if novos == 0:
            break
    return carros


MARCAS_COMPOSTAS = ("LAND ROVER", "ALFA ROMEO", "ASTON MARTIN", "ROLLS ROYCE", "ROYAL ENFIELD", "HARLEY DAVIDSON", "GREAT WALL", "CAOA CHERY")
CAMBIOS = ("Automatizado", "Automático", "Manual", "CVT")


def ler_detalhe(c):
    try:
        h = baixar(c["link"])
    except Exception as e:  # noqa: BLE001
        print(f"  sem detalhe para {c['link']}: {e}", file=sys.stderr)
        h = ""
    carrossel = re.search(r"<Carousel\b.*?</Carousel>", h, re.S | re.I)
    if not carrossel:
        time.sleep(2)
        try:
            h = baixar(c["link"])
        except Exception:  # noqa: BLE001
            pass
        carrossel = re.search(r"<Carousel\b.*?</Carousel>", h, re.S | re.I)
    fotos = []
    if carrossel:
        for src in re.findall(r'<img[^>]+src="([^"]+)"', carrossel.group(0)):
            if src not in fotos:
                fotos.append(src)
    if not fotos and c["capa"]:
        fotos = [c["capa"]]
    c["fotos"] = fotos

    m = re.search(r"<h1[^>]*>(.*?)</h1>", h, re.S)
    c["marca_modelo"] = texto(m.group(1)) if m else ""

    # bloco "2023/2024 - 7659 Km · Elétrico · Automático · R$ ..." logo após o título
    trecho = ""
    m = re.search(r"\d{4}\s*/\s*\d{4}\s*-\s*[\d.]+\s*Km", h)
    if m:
        fim = h.find("R$", m.end())
        trecho = texto(h[m.end(): fim if fim > 0 else m.end() + 3000])
    c["cambio"] = next((x for x in CAMBIOS if x in trecho), "")

    m = re.search(r'<ShareNetwork[^>]*description="([^"]*)"', h, re.I)
    opc = [o.strip() for o in html.unescape(m.group(1)).split(",")] if m else []
    c["opcionais"] = [o for o in opc if o]
    return c


def principal():
    por_id = {}
    for loja, bases in LOJAS:
        base = escolher_base(bases)
        if not base:
            sys.exit(f"Nenhum endereço da loja {loja} respondeu; mantendo o catálogo como está.")
        lista = ler_listagem(loja, base)
        if len(lista) < 3:
            sys.exit(f"Só achei {len(lista)} carros em {base}; o site pode ter mudado. Não vou sobrescrever o catálogo.")
        for c in lista:
            # carro que aparece nos dois sites fica na aba do Outlet
            if c["id"] not in por_id or loja == "outlet":
                por_id[c["id"]] = c
    carros = list(por_id.values())
    with ThreadPoolExecutor(max_workers=4) as ex:
        carros = list(ex.map(ler_detalhe, carros))
    for c in carros:
        nome = c["nome"]
        marca = next((m for m in MARCAS_COMPOSTAS if nome.upper().startswith(m + " ")), nome.split(" ", 1)[0])
        c["marca"] = marca
        c["modelo"] = nome[len(marca):].strip()
    fuso = timezone(timedelta(hours=-3))
    hoje = datetime.now(fuso).strftime("%Y-%m-%d")
    agora = datetime.now(fuso).strftime("%d/%m/%Y %H:%M")

    # histórico: quando o carro entrou e se o preço baixou
    antigo = SAIDA.read_text("utf-8") if SAIDA.exists() else ""
    anteriores = {}
    if antigo:
        try:
            anteriores = {c["id"]: c for c in json.loads(antigo)["carros"]}
        except Exception:  # noqa: BLE001
            anteriores = {}
    for c in carros:
        a = anteriores.get(c["id"])
        if not a:
            c["desde"] = hoje if anteriores else BASE_DATA
            continue
        c["desde"] = a.get("desde") or BASE_DATA
        # se a página de detalhe falhou desta vez, mantém as fotos/dados da leitura anterior
        if len(c.get("fotos") or []) < len(a.get("fotos") or []) and len(c.get("fotos") or []) <= 1:
            c["fotos"] = a["fotos"]
        for k in ("cambio", "opcionais"):
            if not c.get(k) and a.get(k):
                c[k] = a[k]
        if a.get("preco") and c["preco"] and c["preco"] < a["preco"]:
            c["preco_anterior"], c["baixou_em"] = a["preco"], hoje
        elif a.get("preco_anterior") and a.get("baixou_em") and c["preco"] < a["preco_anterior"] \
                and dias_desde(a["baixou_em"], hoje) <= 15:
            c["preco_anterior"], c["baixou_em"] = a["preco_anterior"], a["baixou_em"]

    carros.sort(key=lambda c: (c["loja"], c["marca"], c["preco"]))
    dados = {"atualizado": agora, "total": len(carros), "carros": carros}
    novo = json.dumps(dados, ensure_ascii=False, indent=1)
    # só regrava se o estoque mudou (ignora a data), para não criar commit à toa
    tira = lambda s: re.sub(r'"atualizado": "[^"]*"', "", s)  # noqa: E731
    if tira(novo) == tira(antigo) and (SAIDA.parent / "c").exists():
        print("Estoque sem mudanças.")
        return
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(novo, "utf-8")
    gerar_previas(carros)
    print(f"Catálogo atualizado: {len(carros)} carros.")


BASE_DATA = "2026-01-01"  # carros que já estavam no estoque antes do histórico existir
SITE = "https://docsdigitaiscarmax-spec.github.io/catalogo-carmax/"


def dias_desde(d, hoje):
    return (datetime.strptime(hoje, "%Y-%m-%d") - datetime.strptime(d, "%Y-%m-%d")).days


def brl(v):
    return "R$ " + f"{v:,}".replace(",", ".")


PREVIA = """<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>{titulo}</title>
<meta property="og:type" content="website">
<meta property="og:site_name" content="Carmax Santos">
<meta property="og:title" content="{titulo}">
<meta property="og:description" content="{desc}">
<meta property="og:image" content="{img}">
<meta property="og:url" content="{url}">
<meta name="twitter:card" content="summary_large_image">
<meta http-equiv="refresh" content="0; url=../#carro-{id}">
<script>location.replace('../#carro-{id}')</script>
</head><body><a href="../#carro-{id}">{titulo}</a></body></html>
"""


def gerar_previas(carros):
    """Uma página pequena por carro, só para o WhatsApp mostrar foto e preço no link."""
    pasta = SAIDA.parent / "c"
    pasta.mkdir(exist_ok=True)
    for f in pasta.glob("*.html"):
        f.unlink()
    esc = lambda t: html.escape(str(t), quote=True)  # noqa: E731
    for c in carros:
        km = "0 km" if not c["km"] else f'{c["km"]:,} km'.replace(",", ".")
        desc = f'{brl(c["preco"])} · {c["ano"]} · {km}'
        if c.get("cambio"):
            desc += f' · {c["cambio"]}'
        desc += " · Fale com Nickolas Garcia no WhatsApp"
        (pasta / f'{c["id"]}.html').write_text(PREVIA.format(
            titulo=esc(f'{c["nome"]} {c["ano"]}'), desc=esc(desc),
            img=esc((c["fotos"] or [c["capa"]])[0]), url=esc(f'{SITE}c/{c["id"]}.html'),
            id=esc(c["id"])), "utf-8")
    # foto de capa da página principal = primeiro carro com mais fotos da loja principal
    idx = SAIDA.parent / "index.html"
    capa = max((c for c in carros if c["loja"] == "carmax"), key=lambda c: len(c["fotos"]), default=None)
    if capa and idx.exists():
        t = idx.read_text("utf-8")
        tag = f'<meta property="og:image" content="{esc(capa["fotos"][0])}">'
        t = re.sub(r'<meta property="og:image" content="[^"]*">', tag, t) if 'og:image' in t \
            else t.replace('<meta property="og:type"', tag + '\n<meta property="og:type"', 1)
        idx.write_text(t, "utf-8")

if __name__ == "__main__":
    principal()
