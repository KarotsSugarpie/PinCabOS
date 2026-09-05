# PinCabOS WebApp backgrounds

The WebApp random background rotator expects these five 2K assets in this directory:

- `background-01.webp`
- `background-02.webp`
- `background-03.webp`
- `background-04.webp`
- `background-05.webp`

Runtime URL prefix: `/static/pincabos-assets/background/`.

The rotator is implemented by `/opt/pincabos/web/static/pincabos-background-rotator-v1.js` and is injected globally by `pincabos_appearance_global.py`. It chooses a random background on page load and History API navigation and avoids repeating the previous selection when possible.
