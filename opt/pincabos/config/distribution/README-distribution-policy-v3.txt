PINCABOS — DISTRIBUTION POLICY V3

Règles officielles:
- Garder /opt/pincabos/version.json.
- Ne pas inclure le contenu de /home/pinball/Tables dans la distribution.
- Garder le dossier /home/pinball/Tables comme dossier vide avec .pincabos-keep.
- Garder la structure /opt, /etc, /var, /home.
- Exclure les secrets, caches, machine-id, host SSH keys et anciens logs runtime au moment de créer l'image.
- Ne pas supprimer les tables du système de développement.
