# =============================================================
# PinCabOS — Prompt ROOT
# root@ = rouge
# PinCab = mauve
# OS = orange
# :chemin# = bleu
# =============================================================

PS1='\[\e[1;31m\]root@\[\e[38;5;135m\]PinCab\[\e[38;5;208m\]OS\[\e[1;34m\]:\w# \[\e[0m\]'


# PINCABOS_ROOT_PROMPT_START
# root = rouge | @ = bleu | PinCab = mauve | OS = orange | chemin/# = bleu clair
case "$-" in
    *i*)
        PS1='\[\e[1;31m\]root\[\e[0m\]\[\e[38;5;33m\]@\[\e[0m\]\[\e[38;5;135m\]PinCab\[\e[0m\]\[\e[38;5;208m\]OS\[\e[0m\]\[\e[38;5;117m\]:\w# \[\e[0m\]'
        ;;
esac
# PINCABOS_ROOT_PROMPT_END
