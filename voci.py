#!/usr/bin/env python3
"""
Gestione delle voci per "Allena il tuo udito".

Comandi:
  python3 voci.py genera     Crea i file audio con voci neurali italiane (edge-tts)
                             per tutte le parole e sillabe presenti in index.html
                             (+ quelle in parole_extra.txt, se esiste).
                             Poi aggiorna automaticamente il manifest.
  python3 voci.py manifest   Rilegge la cartella audio/ e riscrive audio/manifest.json.
                             Da lanciare dopo aver aggiunto registrazioni fatte a mano.

Struttura delle cartelle:
  audio/f_elsa/pane.mp3      prefisso f_ = voce femminile
  audio/m_diego/pane.mp3     prefisso m_ = voce maschile
  audio/f_mamma/pane.m4a     registrazioni vere: stessa regola, nome file = parola

Requisito solo per "genera":  pip install edge-tts
"""
import argparse
import asyncio
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AUDIO = ROOT / "audio"
HTML = ROOT / "index.html"
EXTRA = ROOT / "parole_extra.txt"
EXTS = (".mp3", ".m4a", ".wav", ".ogg", ".webm", ".aac")

# Voci neurali italiane di Microsoft Edge (cartella -> nome voce)
VOCI_EDGE = {
    "f_elsa": "it-IT-ElsaNeural",
    "f_isabella": "it-IT-IsabellaNeural",
    "m_diego": "it-IT-DiegoNeural",
}


def norm(word: str) -> str:
    return unicodedata.normalize("NFC", word).strip().lower()


def leggi_parole() -> list[str]:
    """Estrae tutte le coppie ["a","b"] da index.html e aggiunge parole_extra.txt."""
    parole = set()
    if HTML.exists():
        testo = HTML.read_text(encoding="utf-8")
        coppia = re.compile(r"""\[\s*['"]([^'"\[\]]+)['"]\s*,\s*['"]([^'"\[\]]+)['"]\s*\]""")
        for a, b in coppia.findall(testo):
            parole.update((norm(a), norm(b)))
    if EXTRA.exists():
        for riga in EXTRA.read_text(encoding="utf-8").splitlines():
            for p in re.split(r"[\s,;]+", riga):
                if p.strip():
                    parole.add(norm(p))
    parole.discard("")
    return sorted(parole)


async def genera(velocita: str) -> None:
    try:
        import edge_tts
    except ImportError:
        sys.exit("Manca edge-tts. Installa con:  pip install edge-tts")

    parole = leggi_parole()
    print(f"{len(parole)} parole/sillabe da generare per {len(VOCI_EDGE)} voci")
    for cartella, voce in VOCI_EDGE.items():
        dest = AUDIO / cartella
        dest.mkdir(parents=True, exist_ok=True)
        fatte = 0
        for parola in parole:
            file = dest / f"{parola}.mp3"
            if file.exists():
                continue
            try:
                await edge_tts.Communicate(parola, voce, rate=velocita).save(str(file))
                fatte += 1
            except Exception as e:  # una parola fallita non blocca le altre
                print(f"  ! {cartella}/{parola}: {e}")
        print(f"  {cartella}: {fatte} nuovi file")
    scrivi_manifest()


def scrivi_manifest() -> None:
    AUDIO.mkdir(exist_ok=True)
    voices, words = {}, {}
    for cartella in sorted(p for p in AUDIO.iterdir() if p.is_dir()):
        vid = cartella.name
        gender = "female" if vid.startswith("f_") else "male" if vid.startswith("m_") else "other"
        n = 0
        for f in sorted(cartella.iterdir()):
            if f.suffix.lower() in EXTS and not f.name.startswith("."):
                words.setdefault(norm(f.stem), {})[vid] = f.name
                n += 1
        if n:
            voices[vid] = {"gender": gender, "count": n}
    out = AUDIO / "manifest.json"
    out.write_text(json.dumps({"voices": voices, "words": words}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(f"Manifest aggiornato: {len(voices)} voci, {len(words)} parole -> {out}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("genera", help="crea gli audio con voci neurali")
    g.add_argument("--velocita", default="-10%", help="es. -10%%, +0%%, -20%% (default -10%%)")
    sub.add_parser("manifest", help="aggiorna audio/manifest.json")
    args = ap.parse_args()
    if args.cmd == "genera":
        asyncio.run(genera(args.velocita))
    else:
        scrivi_manifest()


if __name__ == "__main__":
    main()
