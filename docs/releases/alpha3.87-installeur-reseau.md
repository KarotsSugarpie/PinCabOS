# Alpha 3.87 — installeur : réseau de la cible, mise à jour, décor, lanceur

Publie sur la flotte le contenu de la PR #178 (mergée après la #186, donc sans release propre).

- Cible sans réseau après une installation neuve en DHCP laissé tel quel (PINCABOS_INSTALLEUR_RESEAU_V2).
- Mise à jour : les dossiers conservés sont fusionnés, le choix réseau de l'installeur est rejoué (PINCABOS_KEEP_MERGE_V1).
- Le décor Miss Tilt des dalles secondaires ne prend plus le focus clavier (PINCABOS_INSTALLEUR_DECOR_FOCUS_V1).
- Haut-parleurs testés un par un, fonds Miss Tilt sur backglass / full DMD / topper pendant l'installation.
- Dossier VPX migré/réparé au premier démarrage (ini complet : mode cabinet, DOF).
- Retour de table : VPinFE réactivé et X rafraîchi (PINCABOS_RETOUR_FRONTEND_V1).
- Layout lightdm : champs vides (`--rate normal`) ; sortie sans mode préféré EDID : mode courant.
- Page Terminée : retirer la clé USB après le clic Redémarrer.

Validé en VM 2 têtes (mise à jour d'un 3.77 et installation neuve) ; ISO de test PinCabOS-Alpha-3.81-PR178 sur le cab de Yann.
