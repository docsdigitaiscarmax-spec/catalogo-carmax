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

BASE = "https://carmaxsantos.com.br"
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


def ler_listagem():
    carros, vistos = [], set()
    for pagina in range(1, 40):
        url = f"{BASE}/estoque" + (f"?page={pagina}" if pagina > 1 else "")
        h = baixar(url)
        artigos = re.findall(r"<article\b.*?</article>", h, re.S | re.I)
        novos = 0
        for art in artigos:
            m = re.search(r'href="(https://carmaxsantos\.com\.br/veiculo/[^"?#]+)', art)
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
        print(f"página {pagina}: {novos} carros")
        if novos == 0:
            break
    return carros


CAMBIOS = ("Automatizado", "Automático", "Manual", "CVT")


def ler_detalhe(c):
    try:
        h = baixar(c["link"])
    except Exception as e:  # noqa: BLE001
        print(f"  sem detalhe para {c['link']}: {e}", file=sys.stderr)
        h = ""
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
    carros = ler_listagem()
    if len(carros) < 5:
        sys.exit(f"Só achei {len(carros)} carros; o site pode ter mudado. Não vou sobrescrever o catálogo.")
    with ThreadPoolExecutor(max_workers=6) as ex:
        carros = list(ex.map(ler_detalhe, carros))
    for c in carros:
        partes = c["nome"].split(" ", 1)
        c["marca"] = partes[0]
        c["modelo"] = partes[1] if len(partes) > 1 else ""
    agora = datetime.now(timezone(timedelta(hours=-3))).strftime("%d/%m/%Y %H:%M")
    dados = {"atualizado": agora, "total": len(carros), "carros": carros}
    novo = json.dumps(dados, ensure_ascii=False, indent=1)
    antigo = SAIDA.read_text("utf-8") if SAIDA.exists() else ""
    # só regrava se o estoque mudou (ignora a data), para não criar commit à toa
    tira = lambda s: re.sub(r'"atualizado": "[^"]*"', "", s)  # noqa: E731
    if tira(novo) == tira(antigo):
        print("Estoque sem mudanças.")
        return
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(novo, "utf-8")
    print(f"Catálogo atualizado: {len(carros)} carros.")


if __name__ == "__main__":
    principal()
