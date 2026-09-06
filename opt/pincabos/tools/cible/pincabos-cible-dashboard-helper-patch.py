from pathlib import Path
import sys

path = Path(sys.argv[1])

if not path.exists():
    raise SystemExit(f"ERROR: helper absent: {path}")

text = path.read_text(encoding="utf-8")

old = """    screens:apply)
      log 'screen topology one-shot apply'
      exec systemctl start pincabos-screen-topology.service
      ;;
"""

new = """    screens:apply)
      log 'screen topology unified apply'
      systemctl restart pincabos-screen-topology-boot.service
      systemctl restart pincabos-vpinfe.service
      echo 'Topologie appliquée et VPinFE redémarré.'
      ;;
"""

if new in text:
    print("NOTICE: Dashboard helper déjà corrigé.")
elif text.count(old) == 1:
    path.write_text(
        text.replace(old, new, 1),
        encoding="utf-8",
    )
    print("OK: Dashboard utilise la topologie unifiée.")
else:
    raise SystemExit(
        "ERROR: bloc screens/apply absent ou non unique."
    )
