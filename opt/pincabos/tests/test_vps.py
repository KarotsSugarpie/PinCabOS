"""pincabos_vps : rattachement des tables a la base VPS et diagnostic (PINCABOS_VPS_V1)."""
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path

from _charge import charger

vps = charger("opt/pincabos/tools/pincabos_vps.py", "pco_vps")

DB = [
    {"id": "BunvWvh9", "name": "Terminator 2 - Judgment Day", "manufacturer": "Williams", "year": 1991,
     "ipdbUrl": "https://www.ipdb.org/machine.cgi?id=2524",
     "romFiles": [{"version": "t2_l8", "urls": [{"url": "https://x/t2_l8.zip"}]}],
     "b2sFiles": [{"id": "b1", "authors": ["A"], "urls": [{"url": "https://x/b2s"}]}],
     "pupPackFiles": [{"id": "p1", "authors": ["B"], "urls": [{"url": "https://x/pup"}]}],
     "povFiles": [{"id": "v1", "authors": ["C"], "urls": [{"url": "https://x/pov"}]}],
     "altColorFiles": [], "tableFiles": [{"version": "1.25"}]},
    {"id": "SW2025", "name": "Star Wars", "manufacturer": "Original", "year": 2025, "romFiles": [], "tableFiles": []},
    {"id": "SW1992", "name": "Star Wars", "manufacturer": "Data East", "year": 1992, "romFiles": [{"version": "stwr_103"}], "tableFiles": []},
    {"id": "SWstern", "name": "Star Wars", "manufacturer": "Stern", "year": 2017, "romFiles": [{"version": "sw_161"}], "tableFiles": []},
    {"id": "fM3IOgUK", "name": "Super Mario Bros.", "manufacturer": "Gottlieb", "year": 1992, "romFiles": [{"version": "smb3"}], "tableFiles": []},
    {"id": "OZ", "name": "The Blizzard Of Ozz", "manufacturer": "Original", "year": 2025, "romFiles": [], "tableFiles": [], "broken": False},
]


def table(d, name, manifest=None, roms=(), zip_files=3, b2s=False, packs=(), pov=False):
    t = Path(d) / name
    t.mkdir()
    (t / "t.vpx").write_bytes(b"vpx")
    if manifest is not None:
        (t / vps.MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
    if roms:
        (t / "pinmame" / "roms").mkdir(parents=True)
        for r in roms:
            with zipfile.ZipFile(t / "pinmame" / "roms" / f"{r}.zip", "w") as z:
                for i in range(zip_files):
                    z.writestr(f"f{i}.bin", b"0")
    if b2s:
        (t / "t.directb2s").write_bytes(b"<DirectB2SData/>")
    if pov:
        (t / "t.pov").write_bytes(b"<POV/>")
    for p in packs:
        (t / "pupvideos" / p).mkdir(parents=True)
        (t / "pupvideos" / p / "screens.pup").write_text("ScreenNum,ScreenDes\n")
    return t


class Rattachement(unittest.TestCase):
    def test_nom_du_dossier(self):
        self.assertEqual(vps.parse_folder("Terminator 2 - Judgment Day (Williams 1991)"), ("Terminator 2 - Judgment Day", "Williams", "1991"))
        self.assertEqual(vps.parse_folder("Pizza Time (Original 2020)"), ("Pizza Time", "Original", "2020"))
        self.assertEqual(vps.parse_folder("Sans parentheses"), ("Sans parentheses", "", ""))

    def test_nom_exact_annee_fabricant(self):
        best, cands, how = vps.match(DB, "Terminator 2 - Judgment Day", "Williams", "1991")
        self.assertEqual(best["id"], "BunvWvh9"); self.assertIn("nom", how)

    def test_ponctuation_et_accents_ignores(self):
        best, _, _ = vps.match(DB, "Super Mario Bros", "Gottlieb", "1992")
        self.assertEqual(best["id"], "fM3IOgUK")

    def test_homonymes_departages_par_annee_puis_fabricant(self):
        best, cands, how = vps.match(DB, "Star Wars", "", "")
        self.assertIsNone(best); self.assertEqual(len(cands), 3)
        best, _, _ = vps.match(DB, "Star Wars", "", "1992")
        self.assertEqual(best["id"], "SW1992")
        best, _, _ = vps.match(DB, "Star Wars", "Stern", "")
        self.assertEqual(best["id"], "SWstern")

    def test_la_rom_departage(self):
        best, _, how = vps.match(DB, "Star Wars", "", "", rom="sw_161")
        self.assertEqual(best["id"], "SWstern"); self.assertIn("rom", how)

    def test_inconnu(self):
        best, cands, how = vps.match(DB, "Table Fantome", "Nobody", "1900")
        self.assertIsNone(best); self.assertEqual(cands, []); self.assertEqual(how, "aucun")


class Manifeste(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def test_identifie_et_ecrit_vpsid(self):
        t = table(self.d, "Terminator 2 - Judgment Day (Williams 1991)", manifest={"title": "Terminator 2 - Judgment Day (Williams 1991)", "manufacturer": "Williams", "year": "1991", "rom": "t2_l8", "vpsid": "", "ipdbid": ""})
        res = vps.identify(t, DB)
        self.assertEqual(res["status"], "ok"); self.assertEqual(res["entry"]["id"], "BunvWvh9")
        self.assertTrue(vps.apply_manifest(t, res))
        man = json.loads((t / vps.MANIFEST).read_text())
        self.assertEqual((man["vpsid"], man["ipdbid"]), ("BunvWvh9", "2524"))
        self.assertEqual(man["vps"]["name"], "Terminator 2 - Judgment Day")
        self.assertFalse(vps.apply_manifest(t, res), "deja ecrit : rien ne change")

    def test_vpsid_deja_present_a_priorite(self):
        t = table(self.d, "Star Wars (Original 2025)", manifest={"title": "Star Wars", "vpsid": "SW1992"})
        res = vps.identify(t, DB)
        self.assertEqual((res["status"], res["how"], res["entry"]["id"]), ("ok", "manifeste", "SW1992"))

    def test_sans_manifeste_le_dossier_suffit(self):
        t = table(self.d, "The Blizzard Of Ozz (Original 2025)")
        res = vps.identify(t, DB)
        self.assertEqual(res["entry"]["id"], "OZ")
        self.assertTrue(vps.apply_manifest(t, res))
        self.assertEqual(json.loads((t / vps.MANIFEST).read_text())["vpsid"], "OZ")

    def test_ambigu_n_ecrit_rien(self):
        t = table(self.d, "Star Wars", manifest={"title": "Star Wars"})
        res = vps.identify(t, DB)
        self.assertEqual(res["status"], "ambigu"); self.assertEqual(len(res["candidates"]), 3)
        self.assertFalse(vps.apply_manifest(t, res))


class Diagnostic(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.t2 = DB[0]

    def test_rom_absente(self):
        t = table(self.d, "T2")
        diag = vps.diagnostic(t, self.t2)
        self.assertEqual(diag["rom"]["status"], "absente")
        self.assertTrue(any("ROM absente" in p for p in vps.problemes(diag)))

    def test_rom_ok_un_seul_fichier_n_est_pas_un_probleme(self):
        t = table(self.d, "T2", roms=("t2_l8",), zip_files=1)
        diag = vps.diagnostic(t, self.t2)
        self.assertEqual(diag["rom"]["status"], "ok")
        self.assertEqual(diag["rom"]["zip_files"], {"t2_l8": 1})
        self.assertEqual(vps.problemes(diag), [])

    def test_zip_illisible(self):
        t = table(self.d, "T2")
        (t / "pinmame" / "roms").mkdir(parents=True); (t / "pinmame" / "roms" / "t2_l8.zip").write_bytes(b"pas un zip")
        self.assertTrue(any("illisible" in p for p in vps.problemes(vps.diagnostic(t, self.t2))))

    def test_pupvideos_vide_n_est_pas_un_pack(self):
        t = table(self.d, "AFM", roms=("afm_113b",))
        (t / "pupvideos").mkdir()
        diag = vps.diagnostic(t, None, "afm_113b")
        self.assertEqual(diag["pup"]["root"], ""); self.assertEqual(vps.problemes(diag), [])

    def test_rom_non_referencee(self):
        t = table(self.d, "T2", roms=("t2_l82",))
        self.assertEqual(vps.diagnostic(t, self.t2)["rom"]["status"], "non referencee")

    def test_table_originale_sans_rom(self):
        t = table(self.d, "Oz")
        diag = vps.diagnostic(t, DB[5])
        self.assertEqual(diag["rom"]["status"], "sans rom"); self.assertTrue(diag["original_sans_rom"])
        self.assertEqual(vps.problemes(diag), [])

    def test_pack_mal_nomme(self):
        t = table(self.d, "TF", roms=("tf_180",), packs=("tf_180og",))
        diag = vps.diagnostic(t, None, "tf_180")
        self.assertIs(diag["pup"]["alias_ok"], False)
        self.assertTrue(any("nom de la ROM" in p for p in vps.problemes(diag)))
        t2 = table(self.d, "TF2", roms=("tf_180",), packs=("tf_180",))
        self.assertIs(vps.diagnostic(t2, None, "tf_180")["pup"]["alias_ok"], True)

    def test_pack_d_une_table_sans_rom_jamais_signale(self):
        t = table(self.d, "Oz", packs=("BlizzardOfOzz",))
        diag = vps.diagnostic(t, DB[5], "BlizzardOfOzz-Data")
        self.assertIsNone(diag["pup"]["alias_ok"]); self.assertEqual(vps.problemes(diag), [])

    def test_pack_sans_screens(self):
        t = table(self.d, "Matrix")
        (t / "pupvideos" / "Matrix").mkdir(parents=True); (t / "pupvideos" / "Matrix" / "a.mp4").write_bytes(b"0")
        diag = vps.diagnostic(t, None)
        self.assertTrue(any("sans screens.pup" in p for p in vps.problemes(diag)))

    def test_b2s_pov_et_liens_vps(self):
        t = table(self.d, "T2", roms=("t2_l8",), b2s=True, pov=True)
        diag = vps.diagnostic(t, self.t2)
        self.assertEqual(diag["b2s"]["present"], ["t.directb2s"]); self.assertEqual(diag["pov"]["present"], ["t.pov"])
        self.assertEqual(diag["pov"]["vps"][0]["url"], "https://x/pov"); self.assertEqual(diag["vpx_versions"], ["1.25"])


class Base(unittest.TestCase):
    def test_statut_sans_base(self):
        d = tempfile.mkdtemp()
        st = vps.db_status(Path(d) / "vpsdb.json", Path(d) / "meta.json")
        self.assertFalse(st["present"])

    def test_scan_temp(self):
        d = tempfile.mkdtemp()
        table(d, "Terminator 2 - Judgment Day (Williams 1991)", roms=("t2_l8",), b2s=True)
        table(d, "Star Wars (Original 2025)")
        os.mkdir(os.path.join(d, "sans-vpx"))
        rows = vps.scan_tables(Path(d), DB, apply=True)
        self.assertEqual([r["status"] for r in rows], ["ok", "ok"])
        self.assertTrue(all(r.get("applied") for r in rows))


if __name__ == "__main__":
    unittest.main()
