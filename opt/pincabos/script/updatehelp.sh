#!/usr/bin/env bash
set -Eeuo pipefail
clear

# ===============================================================
# PINCABOS — AIDE DU SYSTÈME DE MISE À JOUR GETPCOS
# Auteur : PinCabOS
# ===============================================================

BASE_URL="${BASE_URL:-https://pincabos.cc/updates}"
CHANNEL="${CHANNEL:-beta}"

BUILD_ROOT="${BUILD_ROOT:-/opt/pincabos/build/updates/releases}"
MANAGED_PATHS="${MANAGED_PATHS:-/opt/pincabos/update/managed-paths.conf}"
BUILD_SCRIPT="${BUILD_SCRIPT:-/opt/pincabos/script/build-update.sh}"
PUBLISH_SCRIPT="${PUBLISH_SCRIPT:-/opt/pincabos/script/publish-update.sh}"
PUBLIC_AUDIT="${PUBLIC_AUDIT:-/root/audit-pincabos-public-update.sh}"

green=$'\033[1;32m'
orange=$'\033[1;33m'
cyan=$'\033[1;36m'
bold=$'\033[1m'
red=$'\033[1;31m'
reset=$'\033[0m'

go() {
    printf '%sGO [√]%s %s\n' "$green" "$reset" "$*"
}

warn() {
    printf '%sAVERTISSEMENT%s %s\n' "$orange" "$reset" "$*" >&2
}

fail() {
    printf '%sNOGO [X]%s %s\n' "$red" "$reset" "$*" >&2
    exit 1
}

title() {
    printf '\n%s===============================================================%s\n' "$cyan" "$reset"
    printf '%s %s%s\n' "$bold" "$1" "$reset"
    printf '%s===============================================================%s\n' "$cyan" "$reset"
}

section() {
    printf '\n%s=== %s ===%s\n' "$bold" "$1" "$reset"
}

command_block() {
    printf '\n%s%s%s\n' "$cyan" "$1" "$reset"
}

latest_version() {
    local tmp version

    command -v curl >/dev/null 2>&1 || {
        printf 'inconnue'
        return
    }

    tmp="$(mktemp)"
    if ! curl -fsSL --connect-timeout 10 \
        "$BASE_URL/channels/$CHANNEL/latest.json" \
        -o "$tmp"
    then
        rm -f "$tmp"
        printf 'indisponible'
        return
    fi

    if command -v python3 >/dev/null 2>&1; then
        version="$(
            python3 - "$tmp" <<'PY' 2>/dev/null || true
import json
import sys

with open(sys.argv[1], encoding="utf-8") as source:
    print(json.load(source).get("version", "inconnue"))
PY
        )"
    else
        version="$(
            sed -nE 's/.*"version"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/p' "$tmp" |
            head -n 1
        )"
    fi

    rm -f "$tmp"
    printf '%s' "${version:-inconnue}"
}

show_user_message() {
    local version
    version="$(latest_version)"

    cat <<EOF
===============================================================
 PINCABOS — MISE À JOUR POUR LES UTILISATEURS
===============================================================

Version présentement publiée : $version
Canal                         : $CHANNEL
Dépôt officiel                : $BASE_URL

PREMIÈRE INSTALLATION DE GETPCOS
Une seule fois sur un cab qui ne possède pas encore getpcos :

curl -fsSL $BASE_URL/install-getpcos.sh -o /tmp/install-getpcos.sh && sudo bash /tmp/install-getpcos.sh && rm -f /tmp/install-getpcos.sh

INSTALLER LA DERNIÈRE MISE À JOUR

sudo getpcos update

VÉRIFIER SANS INSTALLER

getpcos check

AFFICHER LA VERSION INSTALLÉE

getpcos status

REVENIR À LA VERSION PRÉCÉDENTE EN CAS DE PROBLÈME

sudo getpcos rollback

IMPORTANT
- Ne ferme pas la console pendant la mise à jour.
- Les tables et les réglages personnels ne doivent pas être supprimés.
- getpcos vérifie le SHA256 avant l'installation.
- getpcos crée une sauvegarde avant de remplacer les fichiers.
- En cas d'échec, un rollback automatique est tenté.
- Après la mise à jour, redémarre le cab seulement si le message le demande.

SUPPORT
En cas de problème, envoie le résultat complet de :

getpcos status
systemctl --failed
journalctl -u pincabos-webapp.service -n 100 --no-pager

===============================================================
EOF
}

show_developer_help() {
    local version example_release release_dir
    version="$(latest_version)"
    example_release="alpha2.0-beta.$(date +%Y%m%d).1"
    release_dir="$BUILD_ROOT/$example_release"

    title "PINCABOS — AIDE DÉVELOPPEUR DES MISES À JOUR"

    printf '\nVersion publique actuelle : %s\n' "$version"
    printf 'Canal public             : %s\n' "$CHANNEL"
    printf 'Dépôt                    : %s\n' "$BASE_URL"
    printf 'Liste gérée              : %s\n' "$MANAGED_PATHS"
    printf 'Dossier des releases     : %s\n' "$BUILD_ROOT"

    section "1. Vérifier la liste des chemins distribués"

    command_block "cat $MANAGED_PATHS"

    cat <<'EOF'

Cette liste décide quels fichiers du cab de développement seront placés
dans le paquet. Vérifie-la avant chaque grande release.

Ne distribue jamais automatiquement :
- /home/pinball/Tables
- /home/pinball/.vpinball
- /home/pinball/.config/vpinfe
- /opt/pincabos/web/.venv
- /opt/pincabos/build
- /opt/pincabos/backups
- /opt/pincabos/logs
- les configurations audio, écrans et GPU propres à un utilisateur
EOF

    section "2. Construire une nouvelle release"

    command_block "sudo build-update.sh $example_release $CHANNEL"

    printf '\nChemin qui sera créé :\n%s\n' "$release_dir"

    cat <<'EOF'

Règle de version recommandée :

alpha2.0-beta.AAAAMMJJ.NUMERO

Exemples :
alpha2.0-beta.20260714.1
alpha2.0-beta.20260714.2
alpha2.0-beta.20260715.1

Ne republie pas une version déjà utilisée avec un contenu différent.
Crée toujours un nouveau numéro de release.
EOF

    section "3. Auditer la release avant publication"

    command_block "less $release_dir/files.list"

    command_block "cd $release_dir && sha256sum -c audit.sha256"

    cat <<EOF

Audit automatique des chemins interdits :

grep -nE '(^|/)(__pycache__|.*\.py[co]\$)|^(home/pinball/Tables|home/pinball/\.vpinball|home/pinball/\.config/vpinfe|opt/pincabos/web/\.venv|opt/pincabos/build|opt/pincabos/backups|opt/pincabos/logs|opt/pincabos/cache)(/|\$)' "$release_dir/files.list" && echo "NOGO [X] Chemin interdit" || echo "GO [√] Aucun chemin interdit"
EOF

    section "4. Publier exactement la release auditée"

    command_block "sudo publish-update.sh $release_dir"

    cat <<'EOF'

La publication copie :
- pincabos-update.tar.zst
- files.list
- release.json
- audit.sha256
- getpcos
- getpcos.sha256
- install-getpcos.sh
- channels/beta/latest.json

Le script publie par défaut sur :
- serveur SSH : root@192.168.254.55
- dossier Web : /var/www/html/updates
EOF

    section "5. Auditer le dépôt public"

    if [[ -x "$PUBLIC_AUDIT" ]]; then
        command_block "$PUBLIC_AUDIT"
    else
        command_block "curl -fsSL $BASE_URL/channels/$CHANNEL/latest.json | python3 -m json.tool"
        warn "Script d'audit public absent : $PUBLIC_AUDIT"
    fi

    section "6. Vérifications rapides du dépôt"

    cat <<EOF
for URL in \\
  "$BASE_URL/" \\
  "$BASE_URL/getpcos" \\
  "$BASE_URL/getpcos.sha256" \\
  "$BASE_URL/install-getpcos.sh" \\
  "$BASE_URL/channels/$CHANNEL/latest.json"
do
    CODE="\$(curl -Lso /dev/null -w '%{http_code}' "\$URL")"
    printf '%s  %s\n' "\$CODE" "\$URL"
done
EOF

    section "7. Commande à envoyer aux nouveaux utilisateurs"

    command_block "updatehelp.sh --user"

    printf '\nCette commande affiche uniquement le texte prêt à copier-coller.\n'

    section "8. Commandes getpcos disponibles"

    cat <<'EOF'
sudo getpcos update
    Télécharge, vérifie, sauvegarde et installe la dernière release.

getpcos check
    Compare la version installée à la version disponible.

getpcos status
    Affiche le dépôt, le canal, la version installée et la dernière sauvegarde.

sudo getpcos rollback
    Restaure la dernière sauvegarde enregistrée.
EOF

    section "9. Emplacements importants"

    cat <<'EOF'
Client installé :
/usr/local/sbin/getpcos
/usr/local/bin/getpcos

Configuration du dépôt :
/etc/pincabos/getpcos.conf

État local :
/var/lib/getpcos/installed-version
/var/lib/getpcos/installed-release.json
/var/lib/getpcos/last-backup

Cache :
/var/cache/getpcos

Sauvegardes :
/opt/pincabos/backups/updates

Builds :
/opt/pincabos/build/updates/releases

Dépôt Web :
/var/www/html/updates
EOF

    section "10. Diagnostic utilisateur"

    cat <<'EOF'
getpcos status
getpcos check
systemctl --failed
systemctl status pincabos-webapp.service --no-pager
journalctl -u pincabos-webapp.service -n 100 --no-pager
journalctl -u pincabos-vpinfe.service -n 100 --no-pager
EOF

    section "11. Rollback"

    cat <<'EOF'
Rollback normal :

sudo getpcos rollback

Les sauvegardes sont conservées dans :

/opt/pincabos/backups/updates/

Après un rollback, vérifie :

getpcos status
systemctl --failed
systemctl status pincabos-webapp.service --no-pager
EOF

    section "12. Page publique"

    printf '\n%s/\n' "$BASE_URL"
}

verify_public_repo() {
    local work latest version archive files sha
    work="$(mktemp -d)"
    trap 'rm -rf "$work"' RETURN

    for command_name in curl python3 sha256sum tar diff; do
        command -v "$command_name" >/dev/null 2>&1 ||
            fail "Commande absente : $command_name"
    done

    title "PINCABOS — VÉRIFICATION RAPIDE DU DÉPÔT PUBLIC"

    curl -fsSL "$BASE_URL/" |
        grep -q "PinCabOS Updates" ||
        fail "Page publique invalide."
    go "Page publique accessible."

    curl -fsSL "$BASE_URL/getpcos" -o "$work/getpcos"
    curl -fsSL "$BASE_URL/getpcos.sha256" -o "$work/getpcos.sha256"

    (
        cd "$work"
        sha256sum -c getpcos.sha256
    )

    bash -n "$work/getpcos"
    go "Client getpcos valide."

    latest="$work/latest.json"
    curl -fsSL "$BASE_URL/channels/$CHANNEL/latest.json" -o "$latest"

    readarray -t metadata < <(
        python3 - "$latest" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as source:
    data = json.load(source)

print(data["version"])
print(data["archive"])
print(data["files"])
print(data["sha256"])
PY
    )

    version="${metadata[0]}"
    archive="${metadata[1]}"
    files="${metadata[2]}"
    sha="${metadata[3]}"

    go "Manifeste valide : $version"

    curl -fL "$BASE_URL/$archive" -o "$work/update.tar.zst"
    curl -fL "$BASE_URL/$files" -o "$work/files.list"

    printf '%s  %s\n' "$sha" "$work/update.tar.zst" |
        sha256sum -c -

    go "SHA256 de la release valide."

    sort -u "$work/files.list" > "$work/expected.list"

    tar --zstd -tf "$work/update.tar.zst" |
        sed 's#^\./##' |
        sed '/\/$/d' |
        sort -u > "$work/archive.list"

    diff -u "$work/expected.list" "$work/archive.list" >/dev/null ||
        fail "Archive différente de files.list."

    go "Archive conforme à files.list."
    go "Dépôt prêt pour les utilisateurs."
}

install_self() {
    local source_path target
    source_path="$(readlink -f "$0")"
    target="/opt/pincabos/script/updatehelp.sh"

    [[ ${EUID:-$(id -u)} -eq 0 ]] ||
        fail "Utilise sudo pour installer le script."

    install -d -m 0755 /opt/pincabos/script
    install -m 0755 "$source_path" "$target"
    ln -sfn "$target" /usr/local/sbin/updatehelp.sh
    ln -sfn "$target" /usr/local/bin/updatehelp.sh

    go "Script installé : $target"
    go "Commande disponible : updatehelp.sh"
}

usage() {
    cat <<'EOF'
Usage :
  updatehelp.sh
      Affiche toute l'aide développeur.

  updatehelp.sh --user
      Affiche uniquement le message à envoyer aux utilisateurs.

  updatehelp.sh --verify
      Vérifie le dépôt public sans installer de mise à jour.

  sudo updatehelp.sh --install
      Installe le script dans /opt/pincabos/script et dans le PATH.

  updatehelp.sh --help
      Affiche cette aide courte.
EOF
}

case "${1:-}" in
    "")
        show_developer_help
        ;;
    --user|user)
        show_user_message
        ;;
    --verify|verify|audit)
        verify_public_repo
        ;;
    --install|install)
        install_self
        ;;
    --help|-h|help)
        usage
        ;;
    *)
        usage
        exit 1
        ;;
esac
