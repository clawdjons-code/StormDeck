#!/usr/bin/env python3
"""Serve the static StormDeck PPI bundle viewer for local screenshot/demo work."""
from __future__ import annotations

import argparse
import functools
import http.server
import os
from pathlib import Path
import socketserver
from typing import NamedTuple, Sequence
from urllib.parse import quote
import webbrowser


class ServerRoots(NamedTuple):
    bundle_dir: Path
    project_root: Path
    viewer_path: Path
    serve_dir: Path
    bundle_url_path: str
    viewer_url_path: str


def _url_path_for(path: Path, root: Path) -> str:
    rel = path.relative_to(root).as_posix()
    suffix = "/" if path.is_dir() else ""
    return "/" + quote(rel) + suffix


def resolve_server_roots(bundle_dir: str | Path, project_root: str | Path | None = None) -> ServerRoots:
    """Resolve bundle/project paths without starting the long-lived HTTP server."""
    bundle = Path(bundle_dir).expanduser().resolve()
    project = Path(project_root).expanduser().resolve() if project_root else Path(__file__).resolve().parents[1]
    viewer = project / "viewer" / "ppi_bundle_viewer.html"
    if not bundle.exists():
        raise FileNotFoundError(f"bundle_dir does not exist: {bundle}")
    if not viewer.exists():
        raise FileNotFoundError(f"ppi_bundle_viewer.html not found: {viewer}")
    serve = Path(os.path.commonpath([str(bundle), str(project)])).resolve()
    return ServerRoots(
        bundle_dir=bundle,
        project_root=project,
        viewer_path=viewer,
        serve_dir=serve,
        bundle_url_path=_url_path_for(bundle, serve),
        viewer_url_path=_url_path_for(viewer, serve),
    )


def build_viewer_url(host: str, port: int, viewer_url_path: str, bundle_url_path: str) -> str:
    """Build a screenshot-ready viewer URL with the bundle root prefilled."""
    browser_host = "127.0.0.1" if host in {"", "0.0.0.0", "::"} else host
    return f"http://{browser_host}:{int(port)}{viewer_url_path}?bundleRoot={quote(bundle_url_path, safe='/')}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Serve a StormDeck bundle directory and viewer/ppi_bundle_viewer.html "
            "so operators can load the PPI bundle viewer and take screenshots."
        )
    )
    parser.add_argument("bundle_dir", help="Bundle directory containing ppi_tprt_replay_index.json and quicklooks")
    parser.add_argument("--host", default="127.0.0.1", help="Host/interface to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind (default: 8765)")
    parser.add_argument("--open", action="store_true", help="Open the ppi_bundle_viewer.html URL in the default browser")
    parser.add_argument("--project-root", default=Path(__file__).resolve().parents[1], help=argparse.SUPPRESS)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    roots = resolve_server_roots(args.bundle_dir, args.project_root)
    url = build_viewer_url(args.host, args.port, roots.viewer_url_path, roots.bundle_url_path)

    print(f"Serving StormDeck files from: {roots.serve_dir}")
    print(f"Bundle directory: {roots.bundle_dir}")
    print(f"Viewer file: {roots.viewer_path}")
    print(f"Viewer URL: {url}")
    print("Open this URL to load ppi_bundle_viewer.html and capture demo screenshots.")

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(roots.serve_dir))
    with socketserver.ThreadingTCPServer((args.host, args.port), handler) as httpd:
        httpd.allow_reuse_address = True
        if args.open:
            webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped StormDeck bundle viewer server.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
