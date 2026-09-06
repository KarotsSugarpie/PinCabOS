from pathlib import Path
import re
import sys

target = Path(sys.argv[1])
systemd_root = target / "etc/systemd/system"

legacy_dependencies = {
    "graphical.target",
    "pincabos-display-roles.service",
    "pincabos-display-role-app-sync.service",
    "pincabos-display-role-finalizer.service",
    "pincabos-display-role-normalizer.service",
    "pincabos-screen-topology.service",
    "pincabos-screen-topology.timer",
    "pincabos-screen-topology.path",
}

definitions = {
    "pincabos-dashboard-live.service": {
        "after": [
            "display-manager.service",
            "pincabos-screen-topology-boot.service",
        ],
        "wants": [
            "display-manager.service",
            "pincabos-screen-topology-boot.service",
        ],
    },
    "pincabos-fulldmd-no-title.service": {
        "after": [
            "display-manager.service",
            "pincabos-screen-topology-boot.service",
        ],
        "wants": [
            "display-manager.service",
            "pincabos-screen-topology-boot.service",
        ],
    },
    "pincabos-backglass-bridge.service": {
        "after": [
            "display-manager.service",
            "pincabos-screen-topology-boot.service",
        ],
        "wants": [
            "display-manager.service",
            "pincabos-screen-topology-boot.service",
        ],
    },
    "pincabos-switch-graphical-vt.service": {
        "after": [
            "display-manager.service",
            "pincabos-final-graphical-guard.service",
        ],
        "wants": [
            "display-manager.service",
        ],
    },
}


def unique(values):
    result = []

    for value in values:
        if value and value not in result:
            result.append(value)

    return result


def filter_tokens(tokens):
    return [
        token
        for token in tokens
        if token not in legacy_dependencies
    ]


def rewrite_unit(path, desired_after, desired_wants):
    original = path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    lines = original.splitlines()
    output = []

    section = ""
    unit_dependencies_written = False
    install_target_written = False

    existing_after = []
    existing_wants = []

    def write_unit_dependencies():
        nonlocal unit_dependencies_written

        if unit_dependencies_written:
            return

        final_after = unique(
            filter_tokens(existing_after)
            + desired_after
        )

        final_wants = unique(
            filter_tokens(existing_wants)
            + desired_wants
        )

        if final_after:
            output.append(
                "After=" + " ".join(final_after)
            )

        if final_wants:
            output.append(
                "Wants=" + " ".join(final_wants)
            )

        unit_dependencies_written = True

    for line in lines:
        stripped = line.strip()

        section_match = re.match(
            r"^\[([^\]]+)\]$",
            stripped,
        )

        if section_match:
            if section == "Unit":
                write_unit_dependencies()

            if (
                section == "Install"
                and not install_target_written
            ):
                output.append(
                    "WantedBy=graphical.target"
                )
                install_target_written = True

            section = section_match.group(1)
            output.append(line)
            continue

        if section == "Unit":
            dependency_match = re.match(
                r"^(After|Wants|Requires|Before)"
                r"\s*=\s*(.*)$",
                stripped,
                re.IGNORECASE,
            )

            if dependency_match:
                key = dependency_match.group(1)
                key_lower = key.lower()

                tokens = filter_tokens(
                    dependency_match.group(2).split()
                )

                if key_lower == "after":
                    existing_after.extend(tokens)
                    continue

                if key_lower == "wants":
                    existing_wants.extend(tokens)
                    continue

                if tokens:
                    output.append(
                        key + "=" + " ".join(tokens)
                    )

                continue

        if section == "Install":
            if re.match(
                r"^WantedBy\s*=",
                stripped,
                re.IGNORECASE,
            ):
                continue

        output.append(line)

    if section == "Unit":
        write_unit_dependencies()

    if section == "Install" and not install_target_written:
        output.append("WantedBy=graphical.target")
        install_target_written = True

    if not any(
        line.strip() == "[Install]"
        for line in output
    ):
        output.extend([
            "",
            "[Install]",
            "WantedBy=graphical.target",
        ])

    content = "\n".join(output).rstrip() + "\n"

    path.write_text(
        content,
        encoding="utf-8",
    )


def clean_dropin(path):
    original = path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    output = []

    for line in original.splitlines():
        stripped = line.strip()

        dependency_match = re.match(
            r"^(After|Wants|Requires|Before)"
            r"\s*=\s*(.*)$",
            stripped,
            re.IGNORECASE,
        )

        if dependency_match:
            tokens = filter_tokens(
                dependency_match.group(2).split()
            )

            if tokens:
                output.append(
                    dependency_match.group(1)
                    + "="
                    + " ".join(tokens)
                )

            continue

        wanted_by_match = re.match(
            r"^WantedBy\s*=\s*(.*)$",
            stripped,
            re.IGNORECASE,
        )

        if wanted_by_match:
            tokens = [
                token
                for token in wanted_by_match.group(1).split()
                if token != "multi-user.target"
            ]

            if tokens:
                output.append(
                    "WantedBy=" + " ".join(tokens)
                )

            continue

        output.append(line)

    path.write_text(
        "\n".join(output).rstrip() + "\n",
        encoding="utf-8",
    )


for unit, definition in definitions.items():
    unit_path = systemd_root / unit

    if not unit_path.is_file():
        print(f"NOTICE: unit not present: {unit}")
        continue

    rewrite_unit(
        unit_path,
        definition["after"],
        definition["wants"],
    )

    dropin_dir = systemd_root / f"{unit}.d"

    if dropin_dir.is_dir():
        for dropin in sorted(
            dropin_dir.glob("*.conf")
        ):
            clean_dropin(dropin)

    print(f"Rewritten target unit: {unit}")
