"""Command line entry points for the reference runtime."""

from __future__ import annotations

import argparse
import json

from .mock import MockRobotBackend
from .models import load_manifest
from .runtime import MhsRuntime
from .server import serve_mcp


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lerobot-mhs")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="validate a device profile")
    validate.add_argument("manifest")

    describe = subparsers.add_parser("describe", help="print a device profile")
    describe.add_argument("manifest")

    serve = subparsers.add_parser("serve", help="serve a mock backend through MCP")
    serve.add_argument("manifest")
    serve.add_argument("--mode", choices=("simulation", "dry_run", "physical"))
    serve.add_argument("--transport", choices=("stdio",), default="stdio")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    manifest = load_manifest(args.manifest)
    if args.command == "validate":
        print("Manifest is valid: mhs-compatible/0.1")
        return
    if args.command == "describe":
        print(json.dumps(manifest, indent=2))
        return
    runtime = MhsRuntime(manifest, MockRobotBackend(), mode=args.mode)
    serve_mcp(runtime, transport=args.transport)
