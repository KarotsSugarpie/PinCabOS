# Alpha 3.95 — SSF, dossier VPX, retour de table, multiplayer (bail de contrôle)

Publie sur la flotte les PR #189 et #190, mergées après la #194 (donc sans release propre).

## #189 — retex cab de Yann (3.88)
- Dossier VPX réparé même quand VPX a réécrit l'ini minimal en squelette (PINCABOS_VPX_PREF_REPARATION_V2) : tables en mode cabinet, DOF.
- Profil surround 5.1 / 7.1 de la carte activé avant la garde SSF (PINCABOS_AUDIO_PROFIL_SURROUND_V1).
- Test des haut-parleurs dans l'ordre standard des canaux (`speaker-test -m`, PINCABOS_AUDIO_HP_CHMAP_V1).
- Modes VPX 4 et 5 reconnus comme 7.1 : huit haut-parleurs sur le schéma, latéraux = fronton, avertissement sur carte 5.1 (PINCABOS_AUDIO_71_V1).
- Retour de table : la fenêtre principale « VPinFE Table » est réactivée, pas BG/DMD (PINCABOS_RETOUR_FRONTEND_V2 ; alt-tab obligatoire en 3.88).

## #190 — Karots
- Multiplayer : le Lobby pincabos.cc prend réellement le contrôle des cabinets (bail de contrôle `control.desired`, fail-safe sans contrat serveur).

Validé sur le cab de Yann (retour de table, réparation VPX, profil 5.1). Tests : 416 verts.
