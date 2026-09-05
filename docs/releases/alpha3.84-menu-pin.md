# PinCabOS Alpha 3.84

Release de correction WebApp — épinglage du menu principal.

## Correctif principal

- Le menu `.pincabos-nav` reste réellement fixe au viewport lorsque l’épinglage est activé.
- Le menu est temporairement rattaché au `body` pendant l’épinglage afin d’éviter qu’un parent avec `transform`, `filter` ou `overflow` ne le fasse suivre le scroll.
- Le contenu conserve un décalage égal à la hauteur réelle du menu.
- Le désépinglage restaure exactement l’emplacement et les styles précédents.
- L’observateur DOM est durci pour éviter une boucle de resynchronisation.

## Commits inclus

- `b5172310560c3c83225175aac10a690e6651895a` — fix(webapp): pin main menu to viewport
- `35e4cc4964ab123a1298dcfad832dbfdad2edf0d` — fix(webapp): harden pinned menu observer

Cette PR sert de point de publication pour la Release V4 bêta et doit produire PinCabOS Alpha 3.84.
