#!/usr/bin/env python3
from __future__ import annotations

import argparse
import time

from libdmdutil_wrapper import DMDController
from media import make_test_pattern


def main() -> int:
    parser = argparse.ArgumentParser(description="Example libdmdutil-python sender")
    parser.add_argument("--host", help="ZeDMD Wi-Fi host or IP")
    parser.add_argument("--device", help="ZeDMD USB serial device path")
    parser.add_argument("--pixelcade-device", help="Pixelcade serial device path")
    parser.add_argument("--pin2dmd", action="store_true", help="Enable PIN2DMD output")
    parser.add_argument("--width", type=int, help="Output width override")
    parser.add_argument("--height", type=int, help="Output height override")
    parser.add_argument("--brightness", type=int, default=-1, help="ZeDMD brightness override")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose libdmdutil logging")
    parser.add_argument("--image", help="Optional image path to send once")
    parser.add_argument("--gif", help="Optional GIF path to play")
    parser.add_argument("--fit-mode", choices=["stretch", "contain", "cover"], default="stretch")
    parser.add_argument("--loops", type=int, default=1, help="GIF loops")
    parser.add_argument(
        "--pattern-seconds",
        type=float,
        default=3.0,
        help="If no image or gif is given, show a generated pattern for this many seconds",
    )
    args = parser.parse_args()
    if not any([args.host, args.device, args.pixelcade_device, args.pin2dmd]):
        parser.error("at least one display target is required")

    dmd = DMDController(
        host=args.host,
        device=args.device,
        pixelcade_device=args.pixelcade_device,
        pin2dmd=args.pin2dmd,
        width=args.width,
        height=args.height,
        brightness=args.brightness,
        verbose=args.verbose,
    )
    try:
        info = dmd.load()
        targets = []
        if args.device:
            targets.append(f"ZeDMD USB {args.device}")
        if args.host:
            targets.append(f"ZeDMD Wi-Fi {args.host}")
        if args.pixelcade_device:
            targets.append(f"Pixelcade {args.pixelcade_device}")
        if args.pin2dmd:
            targets.append("PIN2DMD")
        endpoint = ", ".join(targets)
        print(f"Connected to {endpoint}: {info.width}x{info.height}, hd={info.has_hd_display}")

        if args.image:
            dmd.hold_image(args.image, fit_mode=args.fit_mode)
            print(f"Sent image: {args.image}")
            return 0

        if args.gif:
            dmd.play_video(args.gif, loops=args.loops, fit_mode=args.fit_mode)
            dmd.wait()
            print(f"Played animation: {args.gif}")
            return 0

        end_time = time.monotonic() + max(args.pattern_seconds, 0.0)
        step = 0
        while time.monotonic() < end_time:
            frame = make_test_pattern(info.width, info.height, step)
            dmd.send_rgb_frame(frame)
            time.sleep(0.065)
            step += 1
        print("Sent generated test pattern")
        return 0
    finally:
        dmd.unload()


if __name__ == "__main__":
    raise SystemExit(main())
