"""Coordinated backup + isolated restore check. Never restores over the live DB."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ["docker", "compose"]


def run(arguments, **kwargs):
    return subprocess.run(arguments, cwd=ROOT, check=True, **kwargs)


def checksum(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024): digest.update(chunk)
    return digest.hexdigest()


def backup():
    name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(3)
    destination = ROOT / "backups" / name
    destination.mkdir(parents=True)
    running = run(COMPOSE + ["ps", "--status", "running", "--services"], capture_output=True, text=True).stdout.split()
    writers = [service for service in ["frontend", "backend"] if service in running]
    try:
        if writers: run(COMPOSE + ["stop", *writers])
        with (destination / "database.dump").open("wb") as output:
            run(COMPOSE + ["exec", "-T", "db", "pg_dump", "-U", "workspace", "-d", "workspace", "-Fc"], stdout=output)
        code = "import sys,tarfile; t=tarfile.open(fileobj=sys.stdout.buffer,mode='w|'); t.add('/data/files',arcname='files'); t.close()"
        with (destination / "files.tar").open("wb") as output:
            run(COMPOSE + ["run", "--rm", "-T", "--no-deps", "--user", "root", "--entrypoint", "python", "backend", "-c", code], stdout=output)
        manifest = {"format": 1, "created_at": datetime.now(timezone.utc).isoformat(),
                    "files": {name: {"sha256": checksum(destination / name), "size_bytes": (destination / name).stat().st_size}
                              for name in ["database.dump", "files.tar"]}}
        (destination / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    finally:
        if writers: run(COMPOSE + ["start", *reversed(writers)])
    print(f"Backup created: backups/{destination.name}")
    return destination


RESTORE_COMPOSE = '''services:
  db:
    image: postgres:17-alpine
    environment:
      POSTGRES_DB: workspace
      POSTGRES_USER: workspace
      POSTGRES_PASSWORD: ${RESTORE_DB_PASSWORD}
    volumes: [restore_db:/var/lib/postgresql/data]
    healthcheck:
      test: [CMD-SHELL, "pg_isready -U workspace -d workspace"]
      interval: 2s
      timeout: 5s
      retries: 30
  verifier:
    image: workspace-backend:latest
    environment:
      DATABASE_URL: postgresql+psycopg://workspace:${RESTORE_DB_PASSWORD}@db:5432/workspace
      FILE_STORAGE_PATH: /data/files
    volumes: [restore_files:/data/files]
    command: [python, -m, app.file_audit, --verify-checksums, --strict]
volumes:
  restore_db:
  restore_files:
'''


def restore_check(destination):
    destination = destination.resolve()
    if not destination.is_relative_to((ROOT / "backups").resolve()):
        raise SystemExit("Select a backup inside this project's backups directory.")
    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    for name in ["database.dump", "files.tar"]:
        expected = manifest["files"][name]
        path = destination / name
        if path.stat().st_size != expected["size_bytes"] or checksum(path) != expected["sha256"]:
            raise SystemExit(f"Archive integrity check failed: {name}")
    configuration = destination / "restore-check.compose.yaml"
    configuration.write_text(RESTORE_COMPOSE, encoding="utf-8")
    project = "workspace-restore-" + secrets.token_hex(5)
    arguments = COMPOSE + ["-f", str(configuration), "-p", project]
    environment = dict(os.environ, RESTORE_DB_PASSWORD=secrets.token_hex(24))
    try:
        run(arguments + ["up", "-d", "--wait", "db"], env=environment)
        with (destination / "database.dump").open("rb") as source:
            run(arguments + ["exec", "-T", "db", "pg_restore", "-U", "workspace", "-d", "workspace", "--exit-on-error"], stdin=source, env=environment)
        code = "import sys,tarfile; t=tarfile.open(fileobj=sys.stdin.buffer,mode='r|'); t.extractall('/data',filter='data'); t.close()"
        with (destination / "files.tar").open("rb") as source:
            run(arguments + ["run", "--rm", "-T", "--no-deps", "--user", "appuser", "--entrypoint", "python", "verifier", "-c", code], stdin=source, env=environment)
        result = run(arguments + ["run", "--rm", "-T", "--no-deps", "verifier"], env=environment, capture_output=True, text=True)
        report = json.loads(result.stdout.strip().splitlines()[-1])
        (destination / "restore-check.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Isolated restore verified: {report['records']} file records, matching sizes and SHA-256 checksums.")
    finally:
        # This exact random project was created above, has no host ports, and
        # owns only disposable restore volumes. The live project is never used.
        run(arguments + ["down", "-v"], env=environment)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["backup", "restore-check", "backup-and-check"])
    parser.add_argument("directory", nargs="?", type=Path)
    args = parser.parse_args()
    if args.action == "restore-check":
        if not args.directory: parser.error("Provide the backup directory")
        restore_check(args.directory)
    else:
        destination = backup()
        if args.action == "backup-and-check": restore_check(destination)
