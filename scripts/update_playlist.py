#!/usr/bin/env python3
"""
Atualizador de playlist M3U otimizada para SS IPTV
Fonte: https://www.batistaplay.net (API Supabase)
- Testa streams antes de incluir
- Mantém canais que falharam até 6 atualizações consecutivas
- Agrupa por categoria
- Gera M3U limpo com logos e group-title
"""

import json
import os
import sys
import time
import urllib.request
import ssl
import concurrent.futures
from datetime import datetime, timezone
from pathlib import Path

# Configurações
API_URL = "https://vujjtxmgzqsgizgsxafj.supabase.co/rest/v1/channels?select=*%2Ccategories%28name%29&is_active=eq.true&order=channel_number.asc"
API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZ1amp0eG1nenFzZ2l6Z3N4YWZqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTQwMDQ5NjEsImV4cCI6MjA2OTU4MDk2MX0.yL3dHtaHZDk5fjCET06n7YsG3UJTmhq6-qwhwIsXoww"
MAX_FAILS = 6          # Remove só após 6 falhas consecutivas
WORKERS = 20
TIMEOUT = 12
STATE_FILE = Path(__file__).parent.parent / "channels_state.json"
OUTPUT_M3U = Path(__file__).parent.parent / "playlist.m3u"
OUTPUT_STATS = Path(__file__).parent.parent / "stats.json"

# Categorias preferidas (ordem no M3U)
CATEGORY_ORDER = [
    "TV Aberta",
    "Notícias",
    "Filmes",
    "Infantis",
    "Religiosos",
    "Variedades",
    "Recomendados",
    "Internacional",
]

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE


def fetch_channels():
    req = urllib.request.Request(
        API_URL,
        headers={
            "apikey": API_KEY,
            "Authorization": f"Bearer {API_KEY}",
            "User-Agent": "BatistaPlay-M3U-Updater/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=30, context=ssl_ctx) as r:
        return json.loads(r.read().decode())


def test_stream(url: str) -> tuple[bool, str]:
    """Testa se o stream responde e parece um HLS válido."""
    try:
        req = urllib.request.Request(
            url,
            method="GET",
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; IPTVChecker/1.0)",
                "Accept": "*/*",
            },
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=ssl_ctx) as r:
            data = r.read(4096)
            ct = (r.getheader("Content-Type") or "").lower()
            if r.status != 200:
                return False, f"HTTP {r.status}"
            if b"#EXTM3U" in data or b"#EXTINF" in data:
                return True, "ok"
            if "mpegurl" in ct or "application/vnd.apple" in ct or "application/x-mpegurl" in ct:
                return True, "ok"
            # Alguns servidores retornam text/plain
            if data.startswith(b"#") and b"EXT" in data[:50]:
                return True, "ok"
            return False, f"content-type={ct}"
    except Exception as e:
        return False, str(e)[:120]


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def generate_m3u(channels: list[dict]) -> str:
    """Gera M3U otimizado para SS IPTV (group-title + logos)."""
    lines = [
        "#EXTM3U",
        "# Playlist gerada automaticamente a partir de batistaplay.net",
        f"# Atualizado: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "# Otimizada para SS IPTV - use tamanho de botões 'Médio' no app",
        "",
    ]

    # Ordenar por categoria preferida e depois por número do canal
    def sort_key(c):
        cat = (c.get("categories") or {}).get("name") or "Outros"
        try:
            order = CATEGORY_ORDER.index(cat)
        except ValueError:
            order = 999
        return (order, c.get("channel_number") or 9999, c.get("name", ""))

    channels = sorted(channels, key=sort_key)

    current_group = None
    for c in channels:
        cat = (c.get("categories") or {}).get("name") or "Outros"
        name = c.get("name", "Canal").strip()
        logo = c.get("logo_url") or ""
        url = c.get("stream_url") or ""
        num = c.get("channel_number")
        tvg_id = f"bp{num}" if num else ""

        if not url:
            continue

        # Atributos SS IPTV / padrão IPTV
        attrs = [
            f'tvg-id="{tvg_id}"',
            f'tvg-name="{name}"',
            f'tvg-logo="{logo}"' if logo else "",
            f'group-title="{cat}"',
        ]
        attr_str = " ".join(a for a in attrs if a)

        lines.append(f'#EXTINF:-1 {attr_str},{name}')
        lines.append(url)

    return "\n".join(lines) + "\n"


def main():
    print("=== BatistaPlay M3U Updater ===")
    print(f"Início: {datetime.now(timezone.utc).isoformat()}")

    # 1. Buscar canais
    print("Buscando canais da API...")
    try:
        channels = fetch_channels()
    except Exception as e:
        print(f"ERRO ao buscar API: {e}")
        sys.exit(1)
    print(f"  {len(channels)} canais ativos na fonte")

    # 2. Carregar estado anterior
    state = load_state()
    print(f"  Estado anterior: {len(state)} canais rastreados")

    # 3. Testar streams em paralelo
    print(f"Testando streams (workers={WORKERS}, timeout={TIMEOUT}s)...")
    test_results = {}

    def worker(c):
        ok, err = test_stream(c["stream_url"])
        return c["id"], ok, err

    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(worker, c): c for c in channels}
        done = 0
        for fut in concurrent.futures.as_completed(futs):
            cid, ok, err = fut.result()
            test_results[cid] = (ok, err)
            done += 1
            if done % 20 == 0 or done == len(channels):
                print(f"  Progresso: {done}/{len(channels)}")

    # 4. Atualizar estado e decidir quais incluir
    now = datetime.now(timezone.utc).isoformat()
    included = []
    removed = []
    recovered = []
    new_ok = []

    for c in channels:
        cid = c["id"]
        ok, err = test_results.get(cid, (False, "not tested"))
        prev = state.get(cid, {"fail_count": 0, "last_ok": None, "name": c["name"]})

        if ok:
            if prev.get("fail_count", 0) > 0:
                recovered.append(c["name"])
            prev["fail_count"] = 0
            prev["last_ok"] = now
            prev["last_error"] = None
            included.append(c)
            if cid not in state:
                new_ok.append(c["name"])
        else:
            prev["fail_count"] = prev.get("fail_count", 0) + 1
            prev["last_error"] = err
            prev["last_fail"] = now
            if prev["fail_count"] < MAX_FAILS:
                # Ainda na margem de graça – mantém o canal
                included.append(c)
                print(f"  GRAÇA ({prev['fail_count']}/{MAX_FAILS}): {c['name']} – {err}")
            else:
                removed.append(c["name"])
                print(f"  REMOVIDO ({prev['fail_count']} falhas): {c['name']}")

        prev["name"] = c["name"]
        prev["stream_url"] = c["stream_url"]
        prev["category"] = (c.get("categories") or {}).get("name")
        prev["logo_url"] = c.get("logo_url")
        prev["channel_number"] = c.get("channel_number")
        state[cid] = prev

    # Limpar do state canais que não existem mais na fonte há muito tempo
    # (opcional – mantemos por enquanto)

    # 5. Gerar M3U
    m3u = generate_m3u(included)
    OUTPUT_M3U.write_text(m3u, encoding="utf-8")
    save_state(state)

    # 6. Stats
    stats = {
        "updated_at": now,
        "source_total": len(channels),
        "included": len(included),
        "removed_this_run": len(removed),
        "recovered": len(recovered),
        "new": len(new_ok),
        "working_now": sum(1 for ok, _ in test_results.values() if ok),
        "failing_now": sum(1 for ok, _ in test_results.values() if not ok),
    }
    OUTPUT_STATS.write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n=== Resultado ===")
    print(f"  Incluídos no M3U : {len(included)}")
    print(f"  Funcionando agora: {stats['working_now']}")
    print(f"  Falhando agora   : {stats['failing_now']}")
    print(f"  Recuperados      : {len(recovered)}")
    print(f"  Removidos (6+)   : {len(removed)}")
    print(f"  Novos            : {len(new_ok)}")
    print(f"  Arquivo          : {OUTPUT_M3U}")
    print("Concluído.")


if __name__ == "__main__":
    main()
