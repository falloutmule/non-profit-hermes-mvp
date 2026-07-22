#!/usr/bin/env python
"""Fail-closed clean-install acceptance for Non-Profit Hermes.

The harness operates only in a caller-selected disposable cache directory.  It
never installs into, updates, or starts a production Hermes profile.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import tarfile
import subprocess
import sys
import hashlib
import json
import zipfile
from collections import Counter
from pathlib import Path
from pathlib import PurePosixPath
from typing import Callable, NamedTuple, Sequence, TextIO

import yaml


DISPOSABLE_PROFILE_RE = re.compile(r"^nonprofit-v1-test(?:[-_][a-z0-9][a-z0-9_-]*)?$")
RESERVED_PROFILES = frozenset({"default", "nonprofit"})
EXPECTED_COMMANDS = ("daily", "need", "donation", "report", "task", "inventory", "event")
LEGACY_PLUGINS = tuple(f"non-profit-hermes-{name}" for name in EXPECTED_COMMANDS)
EXPECTED_OWNED_PATHS = (
    "distribution.yaml",
    "SOUL.md",
    "config.yaml",
    "skills/non-profit-hermes",
    "plugins/non-profit-hermes",
)
PRIVATE_DIRECTORY_CODES = {
    ".git": "GIT_METADATA",
    "memories": "MEMORY_PATH",
    "sessions": "SESSION_PATH",
    "logs": "LOG_PATH",
    "cache": "CACHE_PATH",
    "caches": "CACHE_PATH",
    "local": "LOCAL_PATH",
    "backups": "BACKUP_PATH",
    "private": "PRIVATE_PATH",
}
RAW_PRIVATE_PATTERNS = (
    ("RAW_TELEGRAM_BOT_TOKEN", re.compile(rb"(?<![A-Za-z0-9_])\d{8,10}:[A-Za-z0-9_-]{30,}")),
    ("RAW_GOOGLE_TOKEN", re.compile(rb"(?<![A-Za-z0-9_])(?:ya29\.|1//)[A-Za-z0-9_-]{12,}")),
    ("RAW_GOOGLE_API_KEY", re.compile(rb"(?<![A-Za-z0-9_])AIza[A-Za-z0-9_-]{20,}")),
    ("RAW_TELEGRAM_PRIVATE_ID", re.compile(rb"(?<!\d)-100\d{8,}(?!\d)")),
    (
        "RAW_AUTHORIZATION",
        re.compile(rb"(?i)authorization\s*[:=]\s*(?:bearer\s+)?[A-Za-z0-9._-]{12,}"),
    ),
    (
        "RAW_CLIENT_SECRET",
        re.compile(
            rb"(?i)\bclient_secret[\"']?\s*:\s*[\"'][A-Za-z0-9._-]{12,}"
        ),
    ),
)


class HarnessError(RuntimeError):
    """A stable, secret-free harness failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class CommandResult(NamedTuple):
    returncode: int
    stdout: str
    stderr: str


class Admission(NamedTuple):
    source: Path
    output_root: Path
    profile: str
    source_head: str
    allowed_cache_root: Path
    active_hermes_root: Path
    isolated_hermes_root: Path


def run_command(
    argv: Sequence[os.PathLike[str] | str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> CommandResult:
    """Run argv without a shell and retain output only in memory."""
    completed = subprocess.run(
        [os.fspath(value) for value in argv],
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        shell=False,
    )
    return CommandResult(completed.returncode, completed.stdout, completed.stderr)


def _require_success(result: CommandResult, code: str, message: str) -> str:
    if result.returncode != 0:
        raise HarnessError(code, message)
    return result.stdout.strip()


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def safe_extract_archive(archive_path: Path, destination: Path) -> tuple[str, ...]:
    """Extract a Git tar archive after validating every member before writes."""
    archive_path = archive_path.resolve()
    destination = destination.resolve()
    if destination.exists():
        raise HarnessError("ARCHIVE_DESTINATION_EXISTS", "archive destination already exists")

    with tarfile.open(archive_path, "r:*") as archive:
        members = archive.getmembers()
        normalized: list[tuple[tarfile.TarInfo, PurePosixPath]] = []
        for member in members:
            name = member.name
            relative = PurePosixPath(name)
            if (
                not name
                or "\\" in name
                or relative.is_absolute()
                or ".." in relative.parts
                or ":" in relative.parts[0]
            ):
                raise HarnessError("ARCHIVE_UNSAFE_PATH", "archive contains an unsafe path")
            if not (member.isfile() or member.isdir()):
                raise HarnessError("ARCHIVE_UNSAFE_TYPE", "archive contains an unsafe member type")
            target = destination.joinpath(*relative.parts).resolve()
            if not _is_within(target, destination):
                raise HarnessError("ARCHIVE_UNSAFE_PATH", "archive contains an unsafe path")
            normalized.append((member, relative))

        destination.mkdir(parents=True)
        extracted: list[str] = []
        for member, relative in normalized:
            target = destination.joinpath(*relative.parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            stream = archive.extractfile(member)
            if stream is None:
                raise HarnessError("ARCHIVE_READ_FAILED", "archive member could not be read")
            with stream, target.open("wb") as output:
                while chunk := stream.read(1024 * 1024):
                    output.write(chunk)
            target.chmod(member.mode & 0o777)
            extracted.append(relative.as_posix())
    return tuple(sorted(extracted))


def _private_path_code(relative: Path) -> str | None:
    lowered_parts = tuple(part.lower() for part in relative.parts)
    filename = lowered_parts[-1]
    if filename == ".env" or (filename.startswith(".env.") and filename != ".env.example"):
        return "DOTENV_FILE"
    if filename == "auth.json":
        return "AUTH_FILE"
    if filename in {"token.json", "credentials.json", "client_secret.json"}:
        return "CREDENTIAL_FILE"
    if filename in {"gateway.pid", "gateway_state.json", "processes.json", "active_profile"}:
        return "RUNTIME_STATE_FILE"
    if filename.endswith((".db", ".sqlite", ".sqlite3", ".db-shm", ".db-wal")):
        return "DATABASE_FILE"
    if filename.endswith(".log"):
        return "LOG_FILE"
    for part in lowered_parts[:-1]:
        if part in PRIVATE_DIRECTORY_CODES:
            return PRIVATE_DIRECTORY_CODES[part]
    return None


def scan_private_material(root: Path) -> dict[str, int]:
    """Return secret-free finding counts for excluded paths and literal patterns."""
    root = root.resolve()
    findings: Counter[str] = Counter()
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().lower()):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        path_code = _private_path_code(relative)
        if path_code:
            findings[path_code] += 1
        data = path.read_bytes()
        # Test modules intentionally exercise redaction with synthetic
        # secret-shaped fixtures. Path exclusions still apply to tests, but
        # literal credential scanning targets distributable/runtime material.
        if relative.parts and relative.parts[0].casefold() == "tests":
            continue
        for code, pattern in RAW_PRIVATE_PATTERNS:
            findings[code] += len(pattern.findall(data))
    return {code: findings[code] for code in sorted(findings) if findings[code]}


def build_isolated_environment(
    admission: Admission,
    inherited: dict[str, str],
) -> tuple[dict[str, str], dict[str, str]]:
    """Build a minimal host-capable environment with no inherited profile or secrets."""
    preserved_names = (
        "PATH",
        "PATHEXT",
        "SYSTEMROOT",
        "WINDIR",
        "COMSPEC",
        "OS",
    )
    environment = {
        name: inherited[name]
        for name in preserved_names
        if name in inherited and inherited[name]
    }
    output = admission.output_root
    environment.update(
        {
            "LOCALAPPDATA": str(output / "platform"),
            "HOME": str(output / "home"),
            "USERPROFILE": str(output / "home"),
            "HERMES_HOME": str(admission.isolated_hermes_root),
            "TMP": str(output / "tmp"),
            "TEMP": str(output / "tmp"),
            "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    return environment, {}


def build_command_plan(
    admission: Admission,
    *,
    extracted: Path,
    install_source: Path,
    wheel: Path,
    venv_python: Path,
    console: Path,
    external_cwd: Path,
) -> dict[str, tuple[str, ...]]:
    """Return the exact argv-only execution contract used by the harness."""
    profile_arguments = (
        "--profile",
        admission.profile,
        "--offline",
        "--strict",
        "--json",
    )
    compile_files = tuple(
        str(path)
        for root in (extracted / "non_profit_hermes", extracted / "scripts", extracted / "tests")
        for path in sorted(root.glob("*.py"))
    )
    return {
        "venv_create": (sys.executable, "-m", "venv", str(admission.output_root / "venv")),
        "wheel_install": (
            str(venv_python),
            "-m",
            "pip",
            "install",
            f"{wheel}[test]",
        ),
        "profile_install": (
            "hermes",
            "profile",
            "install",
            str(install_source),
            "--name",
            admission.profile,
            "-y",
        ),
        "doctor_module": (
            str(venv_python),
            "-m",
            "non_profit_hermes.doctor",
            *profile_arguments,
        ),
        "doctor_console": (str(console), "doctor", *profile_arguments),
        "full_tests": (str(venv_python), "-m", "pytest", "-q"),
        "py_compile": (
            str(venv_python),
            "-m",
            "py_compile",
            *compile_files,
        ),
        "git_diff_check": ("git", "diff", "--check"),
        "external_cwd": (str(external_cwd),),
    }


def build_profile_install_source(
    archive_path: Path,
    destination: Path,
) -> dict[str, object]:
    """Extract a pristine, Git-metadata-free profile-install source.

    The profile-install source must be distinct from the temporary Git-index
    inspection tree: it must contain no ``.git`` directory, no caches, no
    runtime state, and no private material, while retaining every required
    distribution, plugin, package, SOUL, config, and skill asset.
    Returns a deterministic, secret-free provenance summary.
    """
    archive_path = archive_path.resolve()
    destination = destination.resolve()
    if destination.exists():
        raise HarnessError(
            "INSTALL_SOURCE_COLLISION",
            "profile-install source destination already exists",
        )
    extracted_files = safe_extract_archive(archive_path, destination)
    if any(
        Path(*PurePosixPath(relative).parts).parts[0] == ".git"
        for relative in extracted_files
    ):
        raise HarnessError(
            "INSTALL_SOURCE_GIT_METADATA",
            "profile-install source contains Git metadata",
        )
    required = (
        "distribution.yaml",
        "SOUL.md",
        "config.yaml",
        "skills/non-profit-hermes/SKILL.md",
        "plugins/non-profit-hermes/plugin.yaml",
        "plugins/non-profit-hermes/__init__.py",
        "plugins/non-profit-hermes/commands.py",
        "non_profit_hermes/__init__.py",
        "non_profit_hermes/resources/defaults.toml",
        "pyproject.toml",
        "README.md",
    )
    missing = [
        relative
        for relative in required
        if not (destination / Path(*PurePosixPath(relative).parts)).is_file()
    ]
    if missing:
        raise HarnessError(
            "INSTALL_SOURCE_INCOMPLETE",
            "profile-install source is missing required assets",
        )
    if (destination / ".git").exists():
        raise HarnessError(
            "INSTALL_SOURCE_GIT_METADATA",
            "profile-install source contains a .git directory",
        )
    return {
        "archive_sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(),
        "file_count": len(extracted_files),
        "git_metadata_absent": True,
        "required_assets_present": True,
    }


def snapshot_tree(root: Path) -> dict[str, dict[str, int | str]]:
    """Snapshot every profile file by bytes and nanosecond modification time."""
    root = root.resolve()
    snapshot: dict[str, dict[str, int | str]] = {}
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().lower()):
        if not path.is_file():
            continue
        data = path.read_bytes()
        snapshot[path.relative_to(root).as_posix()] = {
            "sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data),
            "mtime_ns": path.stat().st_mtime_ns,
        }
    return snapshot


def verify_doctor_equivalence(
    module_output: str,
    console_output: str,
    *,
    forbidden_values: Sequence[str],
) -> dict[str, object]:
    """Require equivalent healthy doctor JSON without synthetic-value leakage."""
    combined = module_output + "\n" + console_output
    if any(value and value in combined for value in forbidden_values):
        raise HarnessError("DOCTOR_SECRET_LEAK", "doctor output exposed a synthetic private value")
    try:
        module_report = json.loads(module_output)
        console_report = json.loads(console_output)
    except (TypeError, json.JSONDecodeError) as error:
        raise HarnessError("DOCTOR_JSON_INVALID", "doctor did not emit valid JSON") from error
    if not isinstance(module_report, dict) or module_report != console_report:
        raise HarnessError("DOCTOR_REPORT_MISMATCH", "module and console doctor reports differ")
    if module_report.get("exit_code") != 0:
        raise HarnessError("DOCTOR_UNHEALTHY", "offline strict doctor did not report healthy")
    summary = module_report.get("summary")
    if not isinstance(summary, dict):
        raise HarnessError("DOCTOR_JSON_INVALID", "doctor report summary is invalid")
    return {
        "exit_code": 0,
        "mode": module_report.get("mode"),
        "package_version": module_report.get("package_version"),
        "profile": module_report.get("profile"),
        "summary": {key: summary[key] for key in sorted(summary)},
    }


def _read_yaml_mapping(path: Path, code: str) -> dict[str, object]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as error:
        raise HarnessError(code, "required profile YAML is invalid") from error
    if not isinstance(value, dict):
        raise HarnessError(code, "required profile YAML is invalid")
    return value


def inspect_installed_profile(profile_root: Path, expected_profile: str) -> dict[str, bool]:
    """Fail closed on the pre-synthetic installed profile contract."""
    profile_root = profile_root.resolve()
    if not profile_root.is_dir():
        raise HarnessError("PROFILE_NOT_INSTALLED", "disposable profile was not installed")
    findings = scan_private_material(profile_root)
    if findings:
        raise HarnessError("PROFILE_PRIVATE_MATERIAL", "installed profile contains excluded material")

    manifest = _read_yaml_mapping(profile_root / "distribution.yaml", "PROFILE_MANIFEST_INVALID")
    config = _read_yaml_mapping(profile_root / "config.yaml", "PROFILE_CONFIG_INVALID")
    plugins = config.get("plugins")
    plugins = plugins if isinstance(plugins, dict) else {}
    enabled = plugins.get("enabled")
    disabled = plugins.get("disabled")
    owned = manifest.get("distribution_owned")
    legacy_present = any((profile_root / "plugins" / name).exists() for name in LEGACY_PLUGINS)
    gateway_state_present = any(
        (profile_root / filename).exists()
        for filename in ("gateway.pid", "gateway_state.json", "processes.json")
    )
    inventory = {
        "auth_absent_before_synthetic": not (profile_root / "auth.json").exists(),
        "gateway_stopped": not gateway_state_present,
        "legacy_plugins_absent": not legacy_present and disabled == list(LEGACY_PLUGINS),
        "model_correct": config.get("model") == "openai-codex/gpt-5.6-sol",
        "owned_paths_correct": tuple(owned) == EXPECTED_OWNED_PATHS if isinstance(owned, list) else False,
        "private_material_absent": True,
        "unified_plugin_present": (
            enabled == ["non-profit-hermes"]
            and all(
                (profile_root / "plugins" / "non-profit-hermes" / filename).is_file()
                for filename in ("plugin.yaml", "__init__.py", "commands.py")
            )
        ),
        "version_correct": manifest.get("version") == "1.0.0"
        and manifest.get("name") == expected_profile,
    }
    if not all(inventory.values()):
        raise HarnessError("PROFILE_CONTRACT_FAILED", "installed profile contract is incomplete")
    return inventory


def stage_synthetic_configuration(
    profile_root: Path,
    output_root: Path,
    environment: dict[str, str],
) -> tuple[str, ...]:
    """Create unmistakable placeholders only after the exclusion proof passes."""
    if scan_private_material(profile_root):
        raise HarnessError("SYNTHETIC_STAGE_ORDER", "private-material proof must pass before staging")
    synthetic_root = output_root / "synthetic"
    synthetic_root.mkdir(parents=True, exist_ok=False)
    credential = synthetic_root / "google-credentials.json"
    credential.write_text('{"synthetic_disposable_placeholder":true}\n', encoding="utf-8")
    auth_value = "synthetic-disposable-auth-placeholder"
    (profile_root / "auth.json").write_text(
        json.dumps({"openai-codex": {"type": auth_value}}, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    values = {
        "TELEGRAM_BOT_TOKEN": "synthetic-disposable-telegram-placeholder",
        "TELEGRAM_ALLOWED_USERS": "synthetic-disposable-user-placeholder",
        "NON_PROFIT_HERMES_CREDENTIALS_FILE": str(credential),
        "NON_PROFIT_HERMES_SPREADSHEET_ID": "synthetic-disposable-spreadsheet-placeholder",
        "NON_PROFIT_HERMES_CALENDAR_ID": "synthetic-disposable-calendar-placeholder",
    }
    environment.update(values)
    return tuple([auth_value, *values.values()])


def verify_registered_commands(output: str) -> list[str]:
    """Require one registration each for the exact unified command set."""
    try:
        commands = json.loads(output)
    except json.JSONDecodeError as error:
        raise HarnessError("PLUGIN_OUTPUT_INVALID", "plugin verifier did not emit JSON") from error
    if commands != list(EXPECTED_COMMANDS) or len(commands) != len(set(commands)):
        raise HarnessError("PLUGIN_COMMANDS_INVALID", "unified plugin commands are not exact")
    return commands


def verify_wheel_artifact(wheel: Path, extracted_source: Path) -> dict[str, object]:
    """Verify exact package payload, metadata allowlist, entrypoint, and version."""
    wheel = wheel.resolve()
    extracted_source = extracted_source.resolve()
    if not wheel.name.startswith("non_profit_hermes-1.0.0-") or wheel.suffix != ".whl":
        raise HarnessError("WHEEL_VERSION_INVALID", "wheel filename version is not exactly 1.0.0")
    package_root = extracted_source / "non_profit_hermes"
    expected_package = {
        path.relative_to(extracted_source).as_posix()
        for path in package_root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    }
    dist_info = "non_profit_hermes-1.0.0.dist-info"
    expected_metadata = {
        f"{dist_info}/{name}"
        for name in ("METADATA", "WHEEL", "entry_points.txt", "top_level.txt", "RECORD")
    }
    with zipfile.ZipFile(wheel) as archive:
        members = {name for name in archive.namelist() if not name.endswith("/")}
        if members != expected_package | expected_metadata:
            raise HarnessError("WHEEL_MEMBERS_INVALID", "wheel members do not match exact package source")
        entrypoint = archive.read(f"{dist_info}/entry_points.txt").decode("utf-8")
        expected_entrypoint = (
            "[console_scripts]\n"
            "nonprofit-hermes = non_profit_hermes.doctor:main\n"
        )
        if entrypoint != expected_entrypoint:
            raise HarnessError("WHEEL_ENTRYPOINT_INVALID", "wheel console entrypoint is invalid")
        for name in members:
            relative = Path(*PurePosixPath(name).parts)
            if _private_path_code(relative):
                raise HarnessError("WHEEL_PRIVATE_MATERIAL", "wheel contains an excluded path")
            data = archive.read(name)
            if any(pattern.search(data) for _, pattern in RAW_PRIVATE_PATTERNS):
                raise HarnessError("WHEEL_PRIVATE_MATERIAL", "wheel contains a private literal")
    return {
        "console_entrypoint": True,
        "member_count": len(members),
        "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
        "version": "1.0.0",
    }


def verify_sdist_artifact(sdist: Path) -> dict[str, object]:
    """Verify the v1 sdist has only safe regular files under its versioned root."""
    sdist = sdist.resolve()
    expected_root = "non_profit_hermes-1.0.0"
    if sdist.name != f"{expected_root}.tar.gz":
        raise HarnessError("SDIST_VERSION_INVALID", "sdist filename version is not exactly 1.0.0")
    member_count = 0
    with tarfile.open(sdist, "r:gz") as archive:
        for member in archive.getmembers():
            relative = PurePosixPath(member.name)
            if (
                not member.name
                or "\\" in member.name
                or relative.is_absolute()
                or ".." in relative.parts
                or relative.parts[0] != expected_root
            ):
                raise HarnessError("SDIST_UNSAFE_PATH", "sdist contains an unsafe path")
            if not (member.isfile() or member.isdir()):
                raise HarnessError("SDIST_UNSAFE_TYPE", "sdist contains an unsafe member type")
            if member.isdir():
                continue
            member_count += 1
            payload_path = Path(*relative.parts[1:])
            if _private_path_code(payload_path):
                raise HarnessError("SDIST_PRIVATE_MATERIAL", "sdist contains an excluded path")
            stream = archive.extractfile(member)
            if stream is None:
                raise HarnessError("SDIST_READ_FAILED", "sdist member could not be read")
            with stream:
                data = stream.read()
            if any(pattern.search(data) for _, pattern in RAW_PRIVATE_PATTERNS):
                raise HarnessError("SDIST_PRIVATE_MATERIAL", "sdist contains a private literal")
    if member_count == 0:
        raise HarnessError("SDIST_EMPTY", "sdist contains no files")
    return {
        "member_count": member_count,
        "sha256": hashlib.sha256(sdist.read_bytes()).hexdigest(),
        "version": "1.0.0",
    }


def write_result_json(
    path: Path,
    payload: dict[str, object],
    *,
    forbidden_values: Sequence[str],
) -> None:
    """Write canonical result evidence once, rejecting secrets before filesystem writes."""
    if payload.get("production_touched") is not False:
        raise HarnessError("RESULT_PRODUCTION_FLAG", "result must state production_touched false")
    try:
        serialized = json.dumps(payload, sort_keys=True, indent=2) + "\n"
    except (TypeError, ValueError) as error:
        raise HarnessError("RESULT_INVALID", "result payload is not JSON serializable") from error
    if any(value and value in serialized for value in forbidden_values):
        raise HarnessError("RESULT_SECRET_LEAK", "result payload contains a synthetic private value")
    try:
        with path.open("x", encoding="utf-8", newline="\n") as output:
            output.write(serialized)
    except FileExistsError as error:
        raise HarnessError("RESULT_COLLISION", "result evidence already exists") from error


def validate_admission(
    *,
    source: Path,
    output_root: Path,
    profile: str,
    allowed_cache_root: Path,
    active_hermes_root: Path,
    existing_profile_names: set[str] | frozenset[str],
    runner: Callable[..., CommandResult] = run_command,
) -> Admission:
    """Validate every no-write prerequisite and return normalized paths."""
    source = source.resolve()
    output_root = output_root.resolve()
    allowed_cache_root = allowed_cache_root.resolve()
    active_hermes_root = active_hermes_root.resolve()
    isolated_hermes_root = output_root / "platform" / "hermes"

    if not source.is_dir():
        raise HarnessError("SOURCE_MISSING", "source must be an existing directory")
    if output_root.exists():
        raise HarnessError("OUTPUT_COLLISION", "output root must not already exist")
    if not _is_within(output_root, allowed_cache_root) or output_root == allowed_cache_root:
        raise HarnessError("OUTPUT_OUTSIDE_CACHE", "output root must be a new child of the Hermes cache")
    if _is_within(source, output_root) or _is_within(output_root, source):
        raise HarnessError("SOURCE_OUTPUT_OVERLAP", "source and output roots must not overlap")
    if isolated_hermes_root == active_hermes_root:
        raise HarnessError("ACTIVE_ROOT_COLLISION", "isolated Hermes root collides with the active root")

    normalized_profile = profile.strip().lower()
    existing = {name.strip().lower() for name in existing_profile_names}
    if normalized_profile in RESERVED_PROFILES or normalized_profile in existing:
        raise HarnessError("PROFILE_COLLISION", "profile name is reserved or already exists")
    if profile != normalized_profile or not DISPOSABLE_PROFILE_RE.fullmatch(profile):
        raise HarnessError(
            "PROFILE_NOT_DISPOSABLE",
            "profile name must use the nonprofit-v1-test disposable prefix",
        )

    source_text = str(source)
    top_level = _require_success(
        runner(["git", "-C", source_text, "rev-parse", "--show-toplevel"]),
        "SOURCE_NOT_GIT",
        "source must be a Git worktree",
    )
    if Path(top_level).resolve() != source:
        raise HarnessError("SOURCE_NOT_TOPLEVEL", "source must be the Git worktree root")

    source_head = _require_success(
        runner(["git", "-C", source_text, "rev-parse", "HEAD"]),
        "SOURCE_HEAD_INVALID",
        "source HEAD could not be resolved",
    )
    if re.fullmatch(r"[0-9a-f]{40}", source_head) is None:
        raise HarnessError("SOURCE_HEAD_INVALID", "source HEAD must be an exact commit SHA")

    status = _require_success(
        runner(
            [
                "git",
                "-C",
                source_text,
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
            ]
        ),
        "SOURCE_STATUS_FAILED",
        "source cleanliness could not be checked",
    )
    if status:
        raise HarnessError("SOURCE_DIRTY", "source contains tracked or untracked changes")

    help_text = _require_success(
        runner(["hermes", "profile", "install", "--help"]),
        "HERMES_PROFILE_UNSUPPORTED",
        "installed Hermes does not support profile distribution installation",
    )
    if not all(marker in help_text for marker in ("profile install", "--name", "-y")):
        raise HarnessError(
            "HERMES_PROFILE_UNSUPPORTED",
            "installed Hermes profile install contract is unsupported",
        )

    return Admission(
        source=source,
        output_root=output_root,
        profile=profile,
        source_head=source_head,
        allowed_cache_root=allowed_cache_root,
        active_hermes_root=active_hermes_root,
        isolated_hermes_root=isolated_hermes_root,
    )


def _file_hashes(root: Path, relative_files: Sequence[str]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for relative in relative_files:
        path = root / Path(*PurePosixPath(relative).parts)
        if not path.is_file():
            raise HarnessError("SOURCE_ARCHIVE_PARITY", "an archived source file is missing")
        hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def _normalized_argv(
    argv: Sequence[str],
    *,
    admission: Admission,
    extracted: Path,
    wheel: Path | None = None,
    install_source: Path | None = None,
) -> list[str]:
    replacements = [
        (str(extracted), "<EXTRACTED>"),
        (str(admission.output_root), "<OUTPUT>"),
        (str(admission.source), "<SOURCE>"),
    ]
    if install_source is not None:
        replacements.insert(0, (str(install_source), "<INSTALL_SOURCE>"))
    if wheel is not None:
        replacements.insert(0, (str(wheel), "<WHEEL>"))
    normalized: list[str] = []
    for value in argv:
        rendered = str(value)
        for raw, placeholder in replacements:
            rendered = rendered.replace(raw, placeholder)
        normalized.append(rendered.replace("\\", "/"))
    return normalized


def _pytest_summary(output: str) -> str:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    summary = lines[-1] if lines else ""
    if not re.search(r"\b\d+ passed\b", summary) or re.search(
        r"\b(?:failed|error|errors)\b", summary, re.IGNORECASE
    ):
        raise HarnessError("FULL_TESTS_SUMMARY_INVALID", "full pytest success summary is invalid")
    return summary


def _plugin_verifier_code() -> str:
    return """import importlib.util
import json
import socket
import sys
from pathlib import Path

class BlockedSocket(socket.socket):
    def connect(self, *args, **kwargs):
        raise RuntimeError('network disabled')
    def connect_ex(self, *args, **kwargs):
        raise RuntimeError('network disabled')

def blocked(*args, **kwargs):
    raise RuntimeError('network disabled')

socket.socket = BlockedSocket
socket.create_connection = blocked
socket.getaddrinfo = blocked
plugin = Path(sys.argv[1])
name = 'clean_install_non_profit_hermes_plugin'
spec = importlib.util.spec_from_file_location(
    name, plugin / '__init__.py', submodule_search_locations=[str(plugin)]
)
if spec is None or spec.loader is None:
    raise RuntimeError('plugin load failed')
module = importlib.util.module_from_spec(spec)
sys.modules[name] = module
spec.loader.exec_module(module)

class Context:
    def __init__(self):
        self.commands = []
    def register_command(self, command, handler, description='', args_hint=''):
        self.commands.append(command)

context = Context()
module.register(context)
module.register(context)
print(json.dumps(context.commands, separators=(',', ':')))
"""


def run_acceptance(
    admission: Admission,
    *,
    inherited: dict[str, str],
    runner: Callable[..., CommandResult] = run_command,
    build_tool: str | None = None,
) -> dict[str, object]:
    """Execute the accepted disposable workflow and write canonical evidence."""
    output = admission.output_root
    archive_path = output / "source.tar"
    extracted = output / "source"
    install_source = output / "profile-install-source"
    artifacts = output / "artifacts"
    work = output / "work"
    profile_root = admission.isolated_hermes_root / "profiles" / admission.profile
    stages: list[dict[str, str]] = []
    commands: list[dict[str, object]] = []
    forbidden_values: tuple[str, ...] = ()
    active_stage = "archive"
    output.mkdir(parents=False, exist_ok=False)
    artifacts.mkdir()
    work.mkdir()

    def execute(
        stage: str,
        argv: Sequence[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        wheel: Path | None = None,
        install_source_path: Path | None = None,
    ) -> CommandResult:
        result = runner(argv, cwd=cwd, env=env)
        commands.append(
            {
                "stage": stage,
                "argv": _normalized_argv(
                    tuple(str(value) for value in argv),
                    admission=admission,
                    extracted=extracted,
                    wheel=wheel,
                    install_source=install_source_path,
                ),
            }
        )
        if result.returncode != 0:
            raise HarnessError(f"{stage.upper()}_FAILED", f"{stage} command failed")
        return result

    def passed(name: str) -> None:
        stages.append({"name": name, "status": "passed"})

    try:
        execute(
            "archive",
            (
                "git",
                "-c",
                "core.autocrlf=false",
                "archive",
                "--format=tar",
                "--output",
                str(archive_path),
                admission.source_head,
            ),
            cwd=admission.source,
        )
        extracted_files = safe_extract_archive(archive_path, extracted)
        archive_hashes = _file_hashes(extracted, extracted_files)
        passed("archive")

        active_stage = "archive_privacy"
        archive_findings = scan_private_material(extracted)
        if archive_findings:
            raise HarnessError("ARCHIVE_PRIVATE_MATERIAL", "source archive contains excluded material")
        passed("archive_privacy")

        # Recreate a disposable Git index from the already-proven archive.
        # This supports tests that compare canonical files to the index without
        # copying source repository metadata into acceptance evidence.
        active_stage = "archive_git_index"
        execute("archive_git_init", ("git", "init"), cwd=extracted)
        execute(
            "archive_git_identity",
            ("git", "config", "user.name", "clean-install acceptance"),
            cwd=extracted,
        )
        execute(
            "archive_git_email",
            ("git", "config", "user.email", "acceptance@example.invalid"),
            cwd=extracted,
        )
        execute("archive_git_add", ("git", "add", "--all"), cwd=extracted)
        execute(
            "archive_git_commit",
            ("git", "commit", "-m", "acceptance source snapshot"),
            cwd=extracted,
        )
        passed("archive_git_index")

        # Build a pristine profile-install source from the same verified
        # archive. This tree is never contaminated by the temporary Git index
        # created above, so the installed profile receives no .git metadata.
        active_stage = "profile_install_source"
        install_source_evidence = build_profile_install_source(
            archive_path, install_source
        )
        passed("profile_install_source")

        active_stage = "build"
        selected_build_tool = build_tool or ("uv" if shutil.which("uv") else None)
        if selected_build_tool == "uv":
            build_argv = ("uv", "build", "--out-dir", str(artifacts), str(extracted))
        elif selected_build_tool in {"build", "pep517"}:
            build_argv = (
                sys.executable,
                "-m",
                "build",
                "--outdir",
                str(artifacts),
                str(extracted),
            )
        else:
            raise HarnessError("BUILD_TOOL_MISSING", "uv or the isolated PEP 517 build frontend is required")
        execute("build", build_argv, cwd=work)
        wheels = sorted(artifacts.glob("*.whl"))
        sdists = sorted(artifacts.glob("*.tar.gz"))
        if len(wheels) != 1 or len(sdists) != 1:
            raise HarnessError("BUILD_ARTIFACTS_INVALID", "build did not produce exactly one wheel and sdist")
        wheel = wheels[0]
        sdist = sdists[0]
        wheel_evidence = verify_wheel_artifact(wheel, extracted)
        sdist_evidence = verify_sdist_artifact(sdist)
        passed("build")

        environment, _ = build_isolated_environment(admission, inherited)
        for directory in (
            output / "platform",
            output / "home",
            output / "tmp",
        ):
            directory.mkdir(parents=True, exist_ok=True)
        venv_python = output / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        console = output / "venv" / (
            "Scripts/nonprofit-hermes.exe" if os.name == "nt" else "bin/nonprofit-hermes"
        )
        plan = build_command_plan(
            admission,
            extracted=extracted,
            install_source=install_source,
            wheel=wheel,
            venv_python=venv_python,
            console=console,
            external_cwd=work,
        )

        active_stage = "wheel_install"
        execute("venv_create", plan["venv_create"], cwd=work, env=environment)
        execute("wheel_install", plan["wheel_install"], cwd=work, env=environment, wheel=wheel)
        passed("wheel_install")

        active_stage = "profile_install"
        execute(
            "profile_install",
            plan["profile_install"],
            cwd=work,
            env=environment,
            install_source_path=install_source,
        )
        passed("profile_install")

        active_stage = "profile_exclusions"
        profile_inventory = inspect_installed_profile(profile_root, admission.profile)
        passed("profile_exclusions")

        active_stage = "synthetic_configuration"
        forbidden_values = stage_synthetic_configuration(profile_root, output, environment)
        before_doctor = snapshot_tree(profile_root)
        passed("synthetic_configuration")

        active_stage = "doctor_module"
        module_result = execute("doctor_module", plan["doctor_module"], cwd=work, env=environment)
        passed("doctor_module")

        active_stage = "doctor_console"
        console_result = execute("doctor_console", plan["doctor_console"], cwd=work, env=environment)
        passed("doctor_console")

        active_stage = "doctor_equivalence"
        doctor_evidence = verify_doctor_equivalence(
            module_result.stdout,
            console_result.stdout,
            forbidden_values=forbidden_values,
        )
        if snapshot_tree(profile_root) != before_doctor:
            raise HarnessError("DOCTOR_MUTATED_PROFILE", "offline doctor mutated the disposable profile")
        passed("doctor_equivalence")

        active_stage = "plugin_registration"
        plugin_result = execute(
            "plugin_registration",
            (
                str(venv_python),
                "-I",
                "-c",
                _plugin_verifier_code(),
                str(profile_root / "plugins" / "non-profit-hermes"),
            ),
            cwd=work,
            env=environment,
        )
        registered_commands = verify_registered_commands(plugin_result.stdout.strip())
        passed("plugin_registration")

        active_stage = "full_tests"
        tests_result = execute("full_tests", plan["full_tests"], cwd=extracted, env=environment)
        test_summary = _pytest_summary(tests_result.stdout)
        passed("full_tests")

        active_stage = "py_compile"
        execute("py_compile", plan["py_compile"], cwd=work, env=environment)
        passed("py_compile")

        active_stage = "git_diff_check"
        execute("git_diff_check", plan["git_diff_check"], cwd=extracted, env=environment)
        passed("git_diff_check")

        active_stage = "source_archive_parity"
        if _file_hashes(extracted, extracted_files) != archive_hashes:
            raise HarnessError("SOURCE_ARCHIVE_PARITY", "archived source files changed during acceptance")
        passed("source_archive_parity")

        result: dict[str, object] = {
            "schema_version": 1,
            "status": "passed",
            "source_sha": admission.source_head,
            "production_touched": False,
            "stages": stages,
            "commands": commands,
            "artifacts": {"wheel": wheel_evidence, "sdist": sdist_evidence},
            "archive": {
                "file_count": len(extracted_files),
                "private_finding_codes": archive_findings,
                "tracked_files_unchanged": True,
            },
            "profile_install_source": install_source_evidence,
            "doctor": doctor_evidence,
            "profile_inventory": profile_inventory,
            "profile_snapshot_unchanged": True,
            "registered_commands": registered_commands,
            "test_summary": test_summary,
            "limitations": [
                "production profile, network integrations, gateway, and physical-device acceptance were not exercised"
            ],
        }
        write_result_json(output / "result.json", result, forbidden_values=forbidden_values)
        return result
    except HarnessError as error:
        if not stages or stages[-1].get("name") != active_stage:
            stages.append({"name": active_stage, "status": "failed", "code": error.code})
        failure_result: dict[str, object] = {
            "schema_version": 1,
            "status": "failed",
            "source_sha": admission.source_head,
            "production_touched": False,
            "stages": stages,
            "commands": commands,
            "failure_code": error.code,
            "limitations": ["acceptance stopped at the first failed stage"],
        }
        result_path = output / "result.json"
        if not result_path.exists():
            write_result_json(result_path, failure_result, forbidden_values=forbidden_values)
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run clean-install acceptance in a unique disposable directory under "
            "the Hermes cache. Evidence is preserved by default."
        )
    )
    parser.add_argument("--source", type=Path, required=True, help="exact clean Git worktree")
    parser.add_argument(
        "--output-root",
        type=Path,
        required=True,
        help="new unique disposable directory under the Hermes cache",
    )
    parser.add_argument(
        "--profile",
        required=True,
        help="unused disposable profile name beginning nonprofit-v1-test",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="preserve evidence (the safe default; retained for explicitness)",
    )
    parser.add_argument("--json", action="store_true", help="emit a JSON status summary")
    return parser


def _platform_hermes_root(environment: dict[str, str]) -> Path:
    local_app_data = environment.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data).expanduser() / "hermes"
    return Path.home() / ".hermes"


def _existing_profile_names(*roots: Path) -> set[str]:
    names: set[str] = set()
    for root in roots:
        profile_root = root / "profiles"
        if not profile_root.is_dir():
            continue
        names.update(path.name for path in profile_root.iterdir() if path.is_dir())
    return names


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: dict[str, str] | None = None,
    runner: Callable[..., CommandResult] = run_command,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    arguments = build_parser().parse_args(argv)
    inherited = dict(os.environ if environ is None else environ)
    output = sys.stdout if stdout is None else stdout
    error_output = sys.stderr if stderr is None else stderr
    platform_root = _platform_hermes_root(inherited)
    active_root = Path(inherited.get("HERMES_HOME", str(platform_root))).expanduser()
    cache_root = platform_root / "cache"
    existing_names = _existing_profile_names(platform_root, active_root)
    try:
        admission = validate_admission(
            source=arguments.source,
            output_root=arguments.output_root,
            profile=arguments.profile,
            allowed_cache_root=cache_root,
            active_hermes_root=active_root,
            existing_profile_names=existing_names,
            runner=runner,
        )
        result = run_acceptance(admission, inherited=inherited, runner=runner)
    except HarnessError as error:
        if arguments.json:
            output.write(
                json.dumps(
                    {
                        "status": "failed",
                        "failure_code": error.code,
                        "production_touched": False,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            )
        else:
            error_output.write(f"FAILED {error.code}: {error}\n")
        return 1

    if arguments.json:
        output.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    else:
        output.write(
            f"PASSED source_sha={result['source_sha']} evidence={admission.output_root / 'result.json'}\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
