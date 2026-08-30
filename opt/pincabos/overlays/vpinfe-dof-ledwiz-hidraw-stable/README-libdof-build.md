# libdof.so.0.4.7 — build PinCabOS (fix Teensy + Dude's Cab)

- Source : https://github.com/vpinball/libdof, master (eef645d) + fix
  use-after-free dans `DudesCab::Finish()` au teardown
  (PR upstream : https://github.com/vpinball/libdof/pull/65).
- Symptôme corrigé : avec une Dude's Cab ET un TeensyStripController sur le
  même cab, la sortie de table plantait par intermittence
  (`double free` / `free(): invalid pointer`). Trouvé à l'AddressSanitizer.
- sha256 : 97da9d90886c769b278dc5e47756c493e0453b1be9107e7f5027ea97ce9bc6e1
- Validé sur cab réel (Teensy 4.0 backboard 144x16 + Dude's Cab), menu vpinfe
  et en jeu.
- Rollback : version précédente disponible dans l'historique git de ce fichier.
- Quand la PR #65 sera mergée upstream, un simple bump libdof suffira et ce
  build custom pourra disparaître.
