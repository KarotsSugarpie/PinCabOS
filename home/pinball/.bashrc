# =============================================================
# PinCabOS — Prompt PINBALL
# =============================================================

case "$-" in
    *i*)
        PS1='\[\e[1;32m\]pinball\[\e[0m\]\[\e[38;5;33m\]@\[\e[0m\]\[\e[38;5;135m\]PinCab\[\e[0m\]\[\e[38;5;208m\]OS\[\e[0m\]\[\e[38;5;117m\]:\w$ \[\e[0m\]'
        ;;
esac

# PINCABOS_PINBALL_PROMPT_START
# pinball = vert | @ = bleu | PinCab = mauve | OS = orange | chemin/$ = bleu clair
case "$-" in
    *i*)
        PS1='\[\e[1;32m\]pinball\[\e[0m\]\[\e[38;5;33m\]@\[\e[0m\]\[\e[38;5;135m\]PinCab\[\e[0m\]\[\e[38;5;208m\]OS\[\e[0m\]\[\e[38;5;117m\]:\w$ \[\e[0m\]'
        ;;
esac
# PINCABOS_PINBALL_PROMPT_END
