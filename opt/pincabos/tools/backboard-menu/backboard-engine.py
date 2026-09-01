#!/usr/bin/env python3
"""
backboard-engine.py — logique du menu backboard aerao pour PinCabOS / vpinfe.

Sous-commandes :
  build-code <csv> <out_code> <out_map>   Construit le code Custom MX1 (dedup par E)
                                          + le mapping nom_normalise -> event E (JSON).
  matrix-ini <cfgdir>                     Imprime le directoutputconfigNN.ini de la matrice
                                          (N = LedWiz du toy LedStrip lu dans cabinet.xml).
  inject <ini> <code_file>                (Re)injecte le code aerao dans la ligne pinupmenu.
  map <map_json> <tables_dir> [--dry] [--fill-only]
                                          Renseigne FrontendDOFEvent de chaque table installee
                                          par matching de nom. Idempotent. --fill-only ne touche
                                          que les champs vides (les personnalisations manuelles
                                          ne sont jamais ecrasees).
  status <ini> <map_json> <tables_dir>    Etat resume.

Le matching se fait par NOM (la base aerao n'expose pas les roms) : normalisation
(minuscules, sans accents, sans "(Fabricant Annee)", sans ponctuation) puis egalite,
sinon prefixe. En cas d'events multiples pour un nom, preference VPX (E2xxx).
"""
import sys, csv, re, os, glob, json, unicodedata

# marqueur de debut de notre injection dans la ligne pinupmenu (n'apparait que via nous)
INJECT_MARK = "/E2000 WHITE ABL0 ABT0 ABW232"


def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\(.*?\)", "", s)                       # enleve (Fabricant Annee)
    s = re.sub(r"\b(the|a|le|la|of|and|und|der|die)\b", " ", s)
    s = re.sub(r"[^a-z0-9]", "", s)
    return s


def e_rank(e):
    """Ordre de preference : VPX (E2xxx) < FX/FX3 (E4xxx) < FP/autres."""
    n = int(e[1:])
    if 2000 <= n < 3000:
        return (0, n)
    if 4000 <= n < 5000:
        return (1, n)
    return (2, n)


def load_db(csvf):
    rows = list(csv.reader(open(csvf, encoding="utf-8", errors="replace")))
    hdr = rows[0]

    def col(sub):
        for i, h in enumerate(hdr):
            if sub.lower() in h.lower().replace("\n", " "):
                return i
        return -1

    iN, iE, iG = col("Name"), col("E*** Code"), col("GIF ANIMATION")
    if min(iN, iE, iG) < 0:
        sys.exit("CSV: colonnes Name / E*** Code / GIF ANIMATION introuvables")
    db = {}          # norm_name -> list[(event, name)]
    order = []       # codes Custom MX1 dedupliques par event (ordre du CSV)
    seen = set()
    for r in rows[1:]:
        if len(r) <= max(iN, iE, iG):
            continue
        e = r[iE].strip()
        if not re.match(r"^E\d{3,4}$", e):
            continue
        nm = r[iN].split("\n")[0].strip()
        k = norm(nm)
        if k:
            db.setdefault(k, []).append((e, nm))
        code = r[iG].strip().strip("/").replace("\n", " ").strip()
        if code and re.match(r"^E\d", code) and e not in seen:
            seen.add(e)
            order.append(code)
    return db, order


def best_event(events):
    return sorted(set(events), key=e_rank)[0]


def lookup(m, name):
    k = norm(name)
    if not k:
        return None
    if k in m:
        return m[k]
    for kk, v in m.items():
        if kk and (kk.startswith(k) or k.startswith(kk)):
            return v
    return None


def cmd_build_code(csvf, outcode, outmap):
    db, order = load_db(csvf)
    open(outcode, "w", encoding="utf-8").write("/".join(order))
    m = {k: best_event([e for e, _ in lst]) for k, lst in db.items()}
    json.dump(m, open(outmap, "w", encoding="utf-8"))
    print("code=%d entrees  map=%d noms" % (len(order), len(m)))


def _find_pinupmenu_idx(lines):
    incfg = False
    for i, ln in enumerate(lines):
        if ln.strip() == "[Config DOF]":
            incfg = True
        elif incfg and ln.startswith("pinupmenu,"):
            return i
    return -1


def cmd_inject(ini, codefile):
    code = open(codefile, encoding="utf-8").read().strip().strip("/")
    lines = open(ini, encoding="utf-8", errors="replace").read().split("\n")
    i = _find_pinupmenu_idx(lines)
    if i < 0:
        sys.exit("ligne pinupmenu introuvable dans [Config DOF] de " + ini)
    ln = lines[i].rstrip("\r")
    if INJECT_MARK in ln:                 # retire l'injection precedente
        ln = ln[:ln.index(INJECT_MARK)]
    lines[i] = ln + "/" + code
    open(ini, "w", encoding="utf-8").write("\n".join(lines))
    print("inject: code aerao (%d chars) applique a la ligne pinupmenu" % len(code))


def cmd_uninject(ini):
    lines = open(ini, encoding="utf-8", errors="replace").read().split("\n")
    i = _find_pinupmenu_idx(lines)
    if i < 0:
        print("uninject: ligne pinupmenu absente")
        return
    ln = lines[i].rstrip("\r")
    if INJECT_MARK in ln:
        lines[i] = ln[:ln.index(INJECT_MARK)]
        open(ini, "w", encoding="utf-8").write("\n".join(lines))
        print("uninject: code aerao retire de la ligne pinupmenu")
    else:
        print("uninject: rien a retirer")


def cmd_unmap(mapf, tables):
    """Remet a vide les FrontendDOFEvent que l'outil avait poses (== event mappe)."""
    m = json.load(open(mapf, encoding="utf-8")) if os.path.exists(mapf) else {}
    reset = 0
    for t in sorted(glob.glob(os.path.join(tables, "*/"))):
        name = os.path.basename(t.rstrip("/"))
        g = glob.glob(os.path.join(t, "*.info"))
        if not g:
            continue
        info = g[0]
        txt = open(info, encoding="utf-8", errors="replace").read()
        mm = re.search(r'"FrontendDOFEvent"\s*:\s*"([^"]*)"', txt)
        if not mm or not mm.group(1):
            continue
        e = lookup(m, name)
        if e and mm.group(1) == e:                     # ne touche que ce qu'on avait mis
            new = re.sub(r'("FrontendDOFEvent"\s*:\s*")[^"]*(")', r"\g<1>\g<2>", txt, count=1)
            open(info, "w", encoding="utf-8").write(new)
            reset += 1
            print("  - %-42s %s -> \"\"" % (name[:42], e))
    print("unmap: %d table(s) remise(s) a vide" % reset)


def cmd_map(mapf, tables, dry, fill_only=False):
    m = json.load(open(mapf, encoding="utf-8"))
    matched = changed = 0
    miss = []
    for t in sorted(glob.glob(os.path.join(tables, "*/"))):
        name = os.path.basename(t.rstrip("/"))
        g = glob.glob(os.path.join(t, "*.info"))
        if not g:
            continue
        info = g[0]
        e = lookup(m, name)
        if not e:
            miss.append(name)
            continue
        matched += 1
        txt = open(info, encoding="utf-8", errors="replace").read()
        mm = re.search(r'"FrontendDOFEvent"\s*:\s*"([^"]*)"', txt)
        if not mm:
            print("  ! %-42s pas de champ FrontendDOFEvent" % name[:42])
            continue
        cur = mm.group(1)
        if cur == e:
            print("  = %-42s %s" % (name[:42], e))
            continue
        if fill_only and cur:
            # champ deja rempli (personnalisation ou variante) : on respecte
            print("  = %-42s %s (conserve, aerao=%s)" % (name[:42], cur, e))
            continue
        if dry:
            print("  ~ %-42s %s -> %s (dry)" % (name[:42], cur or '""', e))
            continue
        new = re.sub(r'("FrontendDOFEvent"\s*:\s*")[^"]*(")', r"\g<1>" + e + r"\g<2>", txt, count=1)
        open(info, "w", encoding="utf-8").write(new)
        changed += 1
        print("  + %-42s %s -> %s" % (name[:42], cur or '""', e))
    print("--- matched=%d changed=%d unmatched=%d ---" % (matched, changed, len(miss)))
    for u in miss:
        print("  ?? sans logo aerao : " + u)


def cmd_detect(cfgdir):
    """Sortie 0 = backboard HD present (TeensyStripController + LedStrip dans cabinet.xml)."""
    cab = os.path.join(cfgdir, "cabinet.xml")
    if not os.path.exists(cab):
        print("NO_BACKBOARD (pas de cabinet.xml)")
        return 1
    x = open(cab, encoding="utf-8", errors="replace").read()
    has_ctrl = "<TeensyStripController>" in x
    has_strip = "<LedStrip>" in x
    if has_ctrl and has_strip:
        print("HAS_BACKBOARD")
        return 0
    print("NO_BACKBOARD (TeensyStripController=%s LedStrip=%s)" % (has_ctrl, has_strip))
    return 1


def cmd_matrix_ini(cfgdir):
    cab = os.path.join(cfgdir, "cabinet.xml")
    num = None
    if os.path.exists(cab):
        x = open(cab, encoding="utf-8", errors="replace").read()
        mn = re.search(r"<LedStrip>.*?<Name>(.*?)</Name>", x, re.S)
        toy = mn.group(1).strip() if mn else None
        if toy:
            for blk in re.findall(r"<LedWizEquivalent>.*?</LedWizEquivalent>", x, re.S):
                if "<OutputName>%s</OutputName>" % toy in blk:
                    mnum = re.search(r"<LedWizNumber>(\d+)</LedWizNumber>", blk)
                    if mnum:
                        num = mnum.group(1)
                        break
    if num:
        print(os.path.join(cfgdir, "directoutputconfig%s.ini" % num))
        return
    # fallback : le configNN.ini avec le plus d'effets matrice
    best, bn = "", -1
    for f in glob.glob(os.path.join(cfgdir, "directoutputconfig*.ini")):
        c = open(f, encoding="utf-8", errors="replace").read()
        n = c.count("ABW") + c.count("SHP")
        if n > bn:
            bn, best = n, f
    print(best)


def cmd_status(ini, mapf, tables):
    lines = open(ini, encoding="utf-8", errors="replace").read().split("\n")
    i = _find_pinupmenu_idx(lines)
    injected = i >= 0 and INJECT_MARK in lines[i]
    print("matrix ini      : %s" % ini)
    print("code aerao inject: %s" % ("OUI" if injected else "NON"))
    m = json.load(open(mapf, encoding="utf-8")) if os.path.exists(mapf) else {}
    print("base aerao      : %d noms" % len(m))
    ok = no = 0
    for t in sorted(glob.glob(os.path.join(tables, "*/"))):
        name = os.path.basename(t.rstrip("/"))
        g = glob.glob(os.path.join(t, "*.info"))
        if not g:
            continue
        txt = open(g[0], encoding="utf-8", errors="replace").read()
        mm = re.search(r'"FrontendDOFEvent"\s*:\s*"([^"]*)"', txt)
        cur = mm.group(1) if mm else ""
        e = lookup(m, name)
        tag = "OK " if cur else ("map:%s" % e if e else "-- ")
        if cur:
            ok += 1
        else:
            no += 1
        print("  %-42s FrontendDOFEvent=%-7s %s" % (name[:42], cur or '""', tag))
    print("tables avec event=%d sans=%d" % (ok, no))


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    cmd, rest = a[0], a[1:]
    if cmd == "detect":
        sys.exit(cmd_detect(rest[0]))
    elif cmd == "build-code":
        cmd_build_code(*rest[:3])
    elif cmd == "matrix-ini":
        cmd_matrix_ini(rest[0])
    elif cmd == "inject":
        cmd_inject(rest[0], rest[1])
    elif cmd == "uninject":
        cmd_uninject(rest[0])
    elif cmd == "unmap":
        cmd_unmap(rest[0], rest[1])
    elif cmd == "map":
        cmd_map(rest[0], rest[1], "--dry" in rest, "--fill-only" in rest)
    elif cmd == "status":
        cmd_status(rest[0], rest[1], rest[2])
    else:
        sys.exit("commande inconnue: " + cmd)


if __name__ == "__main__":
    main()
