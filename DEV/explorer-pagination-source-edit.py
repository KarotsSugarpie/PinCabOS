from pathlib import Path

path = Path("opt/pincabos/web/app.py")
source = path.read_text(encoding="utf-8")


def replace_once(old, new, label):
    global source
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly 1 anchor, found {count}")
    source = source.replace(old, new, 1)


replace_once(
    '''    # PINCABOS_EXPLORER_NATIVE_TABLES_V1_ROUTE
    pco_native_root = (
        root_name == "Tables"
        and current == root
    )

    # PINCABOS_EXPLORER_CONTROLS_IN_TABLE_V41
''',
    '''    # PINCABOS_EXPLORER_NATIVE_TABLES_V1_ROUTE
    pco_native_root = (
        root_name == "Tables"
        and current == root
    )

    # PINCABOS_EXPLORER_TABLE_PAGINATION_V1
    # Pagination native de la racine Tables. Les autres emplacements
    # conservent leur comportement historique sans pagination.
    pcx_per_page_options = (25, 50, 100, 200)

    try:
        pcx_per_page = int(request.args.get("per_page") or 50)
    except (TypeError, ValueError):
        pcx_per_page = 50

    if pcx_per_page not in pcx_per_page_options:
        pcx_per_page = 50

    try:
        pcx_page = int(request.args.get("page") or 1)
    except (TypeError, ValueError):
        pcx_page = 1

    pcx_page = max(1, pcx_page)
    pcx_pagination_html = ""

    # PINCABOS_EXPLORER_CONTROLS_IN_TABLE_V41
''',
    "pagination argument parsing",
)

replace_once(
    '''    try:
        entries = sorted(current.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
    except Exception:
        entries = []

    for item in entries:
''',
    '''    try:
        entries = sorted(current.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
    except Exception:
        entries = []

    if pco_native_root:
        pcx_total_entries = len(entries)
        pcx_total_pages = max(
            1,
            (pcx_total_entries + pcx_per_page - 1) // pcx_per_page,
        )
        pcx_page = min(pcx_page, pcx_total_pages)
        pcx_start = (pcx_page - 1) * pcx_per_page
        pcx_end = min(pcx_start + pcx_per_page, pcx_total_entries)
        entries = entries[pcx_start:pcx_end]

        def pcx_pagination_url(target_page):
            return "/tools/commander?" + urllib.parse.urlencode(
                {
                    "root": root_name,
                    "path": rel,
                    "page": target_page,
                    "per_page": pcx_per_page,
                }
            )

        pcx_page_numbers = {1, pcx_total_pages}
        pcx_page_numbers.update(
            range(
                max(1, pcx_page - 2),
                min(pcx_total_pages, pcx_page + 2) + 1,
            )
        )

        pcx_nav_parts = []

        if pcx_page > 1:
            pcx_nav_parts.append(
                '<a class="pcx-btn pcx-page-link" href="'
                + esc(pcx_pagination_url(pcx_page - 1))
                + '">‹ Précédent</a>'
            )
        else:
            pcx_nav_parts.append(
                '<span class="pcx-btn pcx-page-disabled" '
                'aria-disabled="true">‹ Précédent</span>'
            )

        pcx_previous_number = None
        for pcx_page_number in sorted(pcx_page_numbers):
            if (
                pcx_previous_number is not None
                and pcx_page_number - pcx_previous_number > 1
            ):
                pcx_nav_parts.append(
                    '<span class="pcx-page-ellipsis" aria-hidden="true">…</span>'
                )

            if pcx_page_number == pcx_page:
                pcx_nav_parts.append(
                    '<span class="pcx-btn pcx-page-link active" '
                    'aria-current="page">'
                    + str(pcx_page_number)
                    + "</span>"
                )
            else:
                pcx_nav_parts.append(
                    '<a class="pcx-btn pcx-page-link" href="'
                    + esc(pcx_pagination_url(pcx_page_number))
                    + '">'
                    + str(pcx_page_number)
                    + "</a>"
                )

            pcx_previous_number = pcx_page_number

        if pcx_page < pcx_total_pages:
            pcx_nav_parts.append(
                '<a class="pcx-btn pcx-page-link" href="'
                + esc(pcx_pagination_url(pcx_page + 1))
                + '">Suivant ›</a>'
            )
        else:
            pcx_nav_parts.append(
                '<span class="pcx-btn pcx-page-disabled" '
                'aria-disabled="true">Suivant ›</span>'
            )

        pcx_per_page_options_html = ""
        for pcx_option in pcx_per_page_options:
            pcx_selected_option = (
                " selected" if pcx_option == pcx_per_page else ""
            )
            pcx_per_page_options_html += (
                '<option value="'
                + str(pcx_option)
                + '"'
                + pcx_selected_option
                + ">"
                + str(pcx_option)
                + "</option>"
            )

        pcx_first_visible = pcx_start + 1 if pcx_total_entries else 0
        pcx_last_visible = pcx_end if pcx_total_entries else 0
        pcx_entry_label = (
            "élément" if pcx_total_entries == 1 else "éléments"
        )

        pcx_pagination_html = (
            '<div class="pcx-pagination" aria-label="Pagination PinCab Explorer">'
            '<div class="pcx-page-summary">'
            + str(pcx_first_visible)
            + "–"
            + str(pcx_last_visible)
            + " sur "
            + str(pcx_total_entries)
            + " "
            + pcx_entry_label
            + "</div>"
            '<nav class="pcx-pagination-nav" aria-label="Pages">'
            + "".join(pcx_nav_parts)
            + "</nav>"
            '<form class="pcx-per-page" method="get" action="/tools/commander">'
            '<input type="hidden" name="root" value="'
            + esc(root_name)
            + '">'
            '<input type="hidden" name="path" value="'
            + esc(rel)
            + '">'
            '<input type="hidden" name="page" value="1">'
            '<label>Par page '
            '<select name="per_page" onchange="this.form.submit()">'
            + pcx_per_page_options_html
            + "</select></label>"
            "</form>"
            "</div>"
        )

    for item in entries:
''',
    "server-side pagination",
)

replace_once(
    '''.pcx-search {
  padding:9px;
  border-radius:8px;
  border:1px solid #333a44;
  background:#0b0d10;
  color:inherit;
  min-width:260px;
}
.pcx-table {
''',
    '''.pcx-search {
  padding:9px;
  border-radius:8px;
  border:1px solid #333a44;
  background:#0b0d10;
  color:inherit;
  min-width:260px;
}
.pcx-pagination {
  display:flex;
  justify-content:space-between;
  align-items:center;
  gap:12px;
  flex-wrap:wrap;
  margin:12px 0;
  padding:10px 12px;
  border:1px solid #242a31;
  border-radius:10px;
  background:#0b0d10;
}
.pcx-pagination-nav {
  display:flex;
  gap:6px;
  align-items:center;
  flex-wrap:wrap;
}
.pcx-page-link.active {
  background:#ff8c00;
  color:#111;
  font-weight:900;
}
.pcx-page-disabled {
  opacity:.45;
  cursor:default;
  pointer-events:none;
}
.pcx-page-ellipsis {
  opacity:.7;
  padding:0 2px;
}
.pcx-per-page {
  display:flex;
  gap:8px;
  align-items:center;
  margin:0;
}
.pcx-per-page select {
  background:#0c0f14;
  color:#f1f4f7;
  border:1px solid #303640;
  border-radius:8px;
  padding:7px 9px;
}
.pcx-page-summary {
  color:#aab2bd;
  font-size:13px;
  white-space:nowrap;
}
.pcx-table {
''',
    "pagination canonical CSS",
)

replace_once(
    '''        <input id="pcxSearch" class="pcx-search" placeholder="Rechercher..." oninput="pcxFilter()">
      </div>

      <div id="pcxList">
''',
    '''        <input id="pcxSearch" class="pcx-search" placeholder="Rechercher..." oninput="pcxFilter()">
      </div>

      __PAGINATION_TOP__

      <div id="pcxList">
''',
    "top pagination slot",
)

replace_once(
    '''      <div id="pcxGrid" class="pcx-grid">
        __CARDS__
      </div>
    </div>
''',
    '''      <div id="pcxGrid" class="pcx-grid">
        __CARDS__
      </div>

      __PAGINATION_BOTTOM__
    </div>
''',
    "bottom pagination slot",
)

replace_once(
    '''    body = body.replace("__PARENT_ROW__", parent_row)
    body = body.replace("__ROWS__", rows)
    body = body.replace("__CARDS__", cards)

    if pco_table_header_tools:
''',
    '''    body = body.replace("__PARENT_ROW__", parent_row)
    body = body.replace("__ROWS__", rows)
    body = body.replace("__CARDS__", cards)
    body = body.replace("__PAGINATION_TOP__", pcx_pagination_html)
    body = body.replace("__PAGINATION_BOTTOM__", pcx_pagination_html)

    if pco_table_header_tools:
''',
    "pagination slot rendering",
)

if "PINCABOS_EXPLORER_TABLE_PAGINATION_V1" not in source:
    raise RuntimeError("pagination marker missing after patch")
if "__PAGINATION_TOP__" not in source or "__PAGINATION_BOTTOM__" not in source:
    raise RuntimeError("pagination placeholders missing after patch")

path.write_text(source, encoding="utf-8")
