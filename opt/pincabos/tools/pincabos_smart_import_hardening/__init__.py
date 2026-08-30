"""PinCabOS Smart Import hardening V2."""
from . import archive, runtime

VERSION = "2"


def install(core):
    public = {}
    # Runtime first: core.run() resolves the patched subprocess proxy.
    public.update(runtime.install(core))
    public.update(archive.install(core))
    return public


def fulldmd_after_success(core):
    runtime.fulldmd_after_success(core)
