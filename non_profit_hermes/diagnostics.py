"""Typed result primitives for deterministic Non-Profit Hermes diagnostics."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
import json
import os
from pathlib import Path
import re
import subprocess
from types import MappingProxyType
from typing import Any, Callable, Iterable, Mapping, Protocol, Sequence

import yaml

from non_profit_hermes import __version__
from non_profit_hermes.config import load_packaged_defaults


class Status(StrEnum):
    """Observable state of one diagnostic check."""

    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    SKIP = "SKIP"


class Severity(IntEnum):
    """Doctor process exit-code severities."""

    HEALTHY = 0
    WARNING = 1
    CONFIGURATION = 2
    RUNTIME = 3
    INTEGRITY = 4


_SENSITIVE_KEY = re.compile(
    r"(?:token|secret|password|authorization|cookie|api[_-]?key)", re.IGNORECASE
)
_SENSITIVE_TEXT = (
    re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{30,}\b"),
    re.compile(r"\bBearer\s+[^\s,;]+", re.IGNORECASE),
    re.compile(r"\bchat[_-]?id\s*[:=]\s*-?\d{8,15}\b", re.IGNORECASE),
    re.compile(r"\b(?:token|secret|password|authorization|cookie|api[_-]?key)\s*[:=]\s*[^\s,;]+", re.IGNORECASE),
    re.compile(r"\bya" + r"29\.[A-Za-z0-9._-]+"),
    re.compile(r"\b1" + r"//[A-Za-z0-9._-]+"),
    re.compile(r"\bAI" + r"za[A-Za-z0-9_-]{20,}"),
    re.compile(r"[A-Za-z]:[\\/](?:Users|Documents and Settings)[\\/][^\s,;]+", re.IGNORECASE),
    re.compile(r"/(?:home|Users)/[^/\s]+(?:/[^\s,;]*)?"),
)


def _redact_text(value: str) -> str:
    sanitized = value
    for pattern in _SENSITIVE_TEXT:
        sanitized = pattern.sub("<redacted>", sanitized)
    return sanitized


def redact(value: Any, *, key: str | None = None) -> Any:
    """Recursively redact known sensitive keys and value patterns."""

    if key is not None and _SENSITIVE_KEY.search(key):
        return "<redacted>"
    if isinstance(value, Mapping):
        return {str(item_key): redact(item, key=str(item_key)) for item_key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item) for item in value)
    if isinstance(value, str):
        return _redact_text(value)
    return value


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


@dataclass(frozen=True)
class CheckResult:
    """Immutable, validated result from one safe diagnostic check."""

    id: str
    category: str
    status: Status
    severity: Severity
    message: str
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not self.id or not self.category or not self.message:
            raise ValueError("check id, category, and message must be non-empty")
        if not isinstance(self.status, Status) or not isinstance(self.severity, Severity):
            raise TypeError("status and severity must use their diagnostic enum types")
        if self.status in {Status.PASS, Status.SKIP} and self.severity is not Severity.HEALTHY:
            raise ValueError("PASS and SKIP checks must be healthy")
        if self.status is Status.WARN and self.severity is not Severity.WARNING:
            raise ValueError("WARN checks must use warning severity")
        if self.status is Status.FAIL and self.severity < Severity.CONFIGURATION:
            raise ValueError("FAIL checks must be blocking")
        object.__setattr__(self, "message", _redact_text(self.message))
        object.__setattr__(self, "metadata", _freeze(redact(self.metadata)))


class Filesystem(Protocol):
    """Read-only filesystem surface used by the doctor."""

    def exists(self, path: Path) -> bool: ...
    def is_file(self, path: Path) -> bool: ...
    def is_dir(self, path: Path) -> bool: ...
    def read_text(self, path: Path) -> str: ...
    def iter_files(self, path: Path) -> Iterable[Path]: ...
    def readable(self, path: Path) -> bool: ...


class LocalFilesystem:
    """Default non-mutating filesystem adapter."""

    def exists(self, path: Path) -> bool:
        return path.exists()

    def is_file(self, path: Path) -> bool:
        return path.is_file()

    def is_dir(self, path: Path) -> bool:
        return path.is_dir()

    def read_text(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def iter_files(self, path: Path) -> Iterable[Path]:
        if path.is_file():
            return (path,)
        if not path.is_dir():
            return ()
        return tuple(sorted(item for item in path.rglob("*") if item.is_file()))

    def readable(self, path: Path) -> bool:
        try:
            with path.open("rb"):
                return True
        except OSError:
            return False


CommandAdapter = Callable[[Sequence[str], Path], Any]


def _run_command(arguments: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(arguments),
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )


@dataclass(frozen=True)
class DoctorReport:
    """Immutable aggregate result for one doctor invocation."""

    mode: str
    profile: str
    strict: bool
    package_version: str
    checks: tuple[CheckResult, ...]
    exit_code: int
    summary: Mapping[str, int]

    def __post_init__(self) -> None:
        object.__setattr__(self, "summary", _freeze(self.summary))


_EXPECTED_VERSION = "1.0.0"
_EXPECTED_MODEL = "openai-codex/gpt-5.6-sol"
_UNIFIED_PLUGIN = "non-profit-hermes"
_LEGACY_PLUGINS = (
    "non-profit-hermes-daily",
    "non-profit-hermes-need",
    "non-profit-hermes-donation",
    "non-profit-hermes-report",
    "non-profit-hermes-task",
    "non-profit-hermes-inventory",
    "non-profit-hermes-event",
)
_EXPECTED_OWNED = (
    "distribution.yaml",
    "SOUL.md",
    "config.yaml",
    "skills/non-profit-hermes",
    "plugins/non-profit-hermes",
)
_REQUIRED_ENVIRONMENT = (
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_ALLOWED_USERS",
    "NON_PROFIT_HERMES_CREDENTIALS_FILE",
    "NON_PROFIT_HERMES_SPREADSHEET_ID",
)
_PRIVATE_PARTS = {
    ".env",
    "auth.json",
    "session",
    "sessions",
    "memory",
    "memories",
    "state",
    "logs",
    "cache",
    "local",
    "private",
}


class DoctorRunner:
    """Run deterministic package, profile, distribution, and privacy checks."""

    def __init__(
        self,
        *,
        profile: str = "nonprofit",
        profile_root: str | Path | None = None,
        package_root: str | Path | None = None,
        distribution_root: str | Path | None = None,
        source_root: str | Path | None = None,
        installed_plugin_roots: Sequence[str | Path] = (),
        home: str | Path | None = None,
        environ: Mapping[str, str] | None = None,
        filesystem: Filesystem | None = None,
        command_adapter: CommandAdapter | None = None,
    ) -> None:
        self.profile = profile
        self._profile_root = Path(profile_root) if profile_root is not None else None
        self.package_root = (
            Path(package_root) if package_root is not None else Path(__file__).resolve().parent
        )
        self.distribution_root = (
            Path(distribution_root) if distribution_root is not None else None
        )
        self.source_root = Path(source_root) if source_root is not None else None
        self.installed_plugin_roots = tuple(Path(path) for path in installed_plugin_roots)
        self.home = Path(home) if home is not None else Path.home()
        self.environ = dict(os.environ if environ is None else environ)
        self.fs = filesystem or LocalFilesystem()
        self.command_adapter = command_adapter or _run_command

    def _resolve_profile_root(self) -> Path:
        if self._profile_root is not None:
            return self._profile_root
        try:
            from hermes_cli.profiles import get_profile_dir

            return Path(get_profile_dir(self.profile))
        except (ImportError, ModuleNotFoundError):
            hermes_home = self.environ.get("HERMES_HOME")
            base = Path(hermes_home) if hermes_home else self.home / ".hermes"
            return base / "profiles" / self.profile

    def _profile(self) -> Path:
        return self._resolve_profile_root()

    def _distribution(self) -> Path:
        return self.distribution_root or self._profile()

    def _yaml_mapping(self, path: Path) -> Mapping[str, Any] | None:
        try:
            value = yaml.safe_load(self.fs.read_text(path))
        except (OSError, UnicodeError, yaml.YAMLError):
            return None
        return value if isinstance(value, Mapping) else None

    @staticmethod
    def _pass(check_id: str, category: str, message: str, **metadata: Any) -> CheckResult:
        return CheckResult(
            id=check_id,
            category=category,
            status=Status.PASS,
            severity=Severity.HEALTHY,
            message=message,
            metadata=metadata,
        )

    @staticmethod
    def _skip(check_id: str, category: str, message: str) -> CheckResult:
        return CheckResult(
            id=check_id,
            category=category,
            status=Status.SKIP,
            severity=Severity.HEALTHY,
            message=message,
        )

    @staticmethod
    def _warn(check_id: str, category: str, message: str) -> CheckResult:
        return CheckResult(
            id=check_id,
            category=category,
            status=Status.WARN,
            severity=Severity.WARNING,
            message=message,
        )

    @staticmethod
    def _fail(
        check_id: str,
        category: str,
        message: str,
        severity: Severity = Severity.CONFIGURATION,
    ) -> CheckResult:
        return CheckResult(
            id=check_id,
            category=category,
            status=Status.FAIL,
            severity=severity,
            message=message,
        )

    def _check_package_import(self) -> CheckResult:
        init_path = self.package_root / "__init__.py"
        if not self.fs.is_file(init_path):
            return self._fail("package.import", "package", "canonical package import file is missing")
        return self._pass("package.import", "package", "canonical package import path is present")

    def _check_package_version(self) -> CheckResult:
        if __version__ != _EXPECTED_VERSION:
            return self._fail(
                "package.version",
                "package",
                "package version does not match the v1 contract",
                Severity.INTEGRITY,
            )
        return self._pass(
            "package.version", "package", "package version matches", version=__version__
        )

    def _check_package_defaults(self) -> CheckResult:
        try:
            defaults = load_packaged_defaults()
        except (OSError, ValueError, TypeError):
            return self._fail(
                "package.defaults",
                "package",
                "packaged defaults could not be loaded",
                Severity.INTEGRITY,
            )
        if defaults.get("version") != __version__:
            return self._fail(
                "package.defaults",
                "package",
                "packaged defaults version does not match package version",
                Severity.INTEGRITY,
            )
        return self._pass("package.defaults", "package", "packaged defaults load and match")

    def _check_package_files(self) -> CheckResult:
        expected = (
            "__init__.py",
            "config.py",
            "diagnostics.py",
            "doctor.py",
            "models.py",
            "oauth_refresh.py",
            "operations.py",
            "router.py",
            "resources/defaults.toml",
        )
        missing = [relative for relative in expected if not self.fs.is_file(self.package_root / relative)]
        if missing:
            return self._fail(
                "package.files",
                "package",
                "canonical package files are missing",
                Severity.INTEGRITY,
            )
        return self._pass("package.files", "package", "canonical package files are present")

    def _check_source_commit(self) -> CheckResult:
        if self.source_root is None or not self.fs.exists(self.source_root / ".git"):
            return self._skip(
                "package.source_commit", "package", "source commit is unavailable outside a source checkout"
            )
        result = self.command_adapter(("git", "rev-parse", "HEAD"), self.source_root)
        return_code = getattr(result, "returncode", 1)
        stdout = str(getattr(result, "stdout", "")).strip()
        if return_code != 0 or not re.fullmatch(r"[0-9a-fA-F]{40}", stdout):
            return self._warn("package.source_commit", "package", "source commit could not be read")
        return self._pass(
            "package.source_commit", "package", "source commit discovered", source_commit=stdout.lower()
        )

    def _check_package_safety(self) -> CheckResult:
        forbidden_text = (
            "sys" + ".path",
            "from " + "scripts",
            "import " + "scripts",
        )
        literal_patterns = (
            re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{30,}\b"),
            re.compile(r"\bya" + r"29\.[A-Za-z0-9._-]+"),
            re.compile(r"\b1" + r"//[A-Za-z0-9._-]+"),
            re.compile(r"\bAI" + r"za[A-Za-z0-9_-]{20,}"),
            re.compile(r"[A-Za-z]:[\\/]Users[\\/][^\\/\s]+", re.IGNORECASE),
            re.compile(r"/(?:home|Users)/[^/\s]+/"),
            re.compile(r"\bchat[_-]?id\s*[:=]\s*-?\d{8,15}\b", re.IGNORECASE),
        )
        for path in self.fs.iter_files(self.package_root):
            if path.suffix.lower() not in {".py", ".toml"}:
                continue
            try:
                source = self.fs.read_text(path)
            except (OSError, UnicodeError):
                return self._fail(
                    "package.source_safety",
                    "package",
                    "canonical package source could not be inspected",
                    Severity.INTEGRITY,
                )
            if any(marker in source for marker in forbidden_text) or any(
                pattern.search(source) for pattern in literal_patterns
            ):
                return self._fail(
                    "package.source_safety",
                    "package",
                    "canonical package source contains a forbidden portability or secret pattern",
                    Severity.INTEGRITY,
                )
        return self._pass(
            "package.source_safety", "package", "canonical package source passes safety scan"
        )

    def _check_profile_exists(self) -> CheckResult:
        if not self.fs.is_dir(self._profile()):
            return self._fail("profile.exists", "profile", "profile directory is missing")
        return self._pass("profile.exists", "profile", "profile directory is present")

    def _check_profile_config(self) -> CheckResult:
        config = self._yaml_mapping(self._profile() / "config.yaml")
        if config is None:
            return self._fail("profile.config", "profile", "profile config is missing or invalid")
        plugins = config.get("plugins")
        if not isinstance(plugins, Mapping):
            return self._fail("profile.config", "profile", "profile plugin configuration is invalid")
        enabled = plugins.get("enabled")
        disabled = plugins.get("disabled")
        if not isinstance(enabled, list) or not isinstance(disabled, list):
            return self._fail("profile.config", "profile", "profile plugin lists are invalid")
        if config.get("model") != _EXPECTED_MODEL:
            return self._fail("profile.config", "profile", "profile model route does not match")
        if enabled.count(_UNIFIED_PLUGIN) != 1:
            return self._fail("profile.config", "profile", "unified plugin is not enabled exactly once")
        if any(name in enabled for name in _LEGACY_PLUGINS):
            return self._fail("profile.config", "profile", "unified and legacy plugins overlap")
        if any(name not in disabled for name in _LEGACY_PLUGINS):
            return self._fail("profile.config", "profile", "legacy plugins are not all disabled")
        return self._pass("profile.config", "profile", "model and plugin route match")

    def _check_profile_plugin(self) -> CheckResult:
        candidates = (self._profile() / "plugins", *self.installed_plugin_roots)
        for root in candidates:
            plugin = root / _UNIFIED_PLUGIN
            if all(
                self.fs.is_file(plugin / relative)
                for relative in ("plugin.yaml", "__init__.py", "commands.py")
            ):
                return self._pass("profile.plugin", "profile", "unified plugin is discoverable")
        return self._fail("profile.plugin", "profile", "unified plugin is not discoverable")

    def _check_profile_auth(self) -> CheckResult:
        path = self._profile() / "auth.json"
        if not self.fs.is_file(path):
            return self._fail("profile.auth", "profile", "auth metadata file is missing")
        try:
            value = json.loads(self.fs.read_text(path))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return self._fail("profile.auth", "profile", "auth metadata file is invalid")
        if not isinstance(value, Mapping):
            return self._fail("profile.auth", "profile", "auth metadata root is not a mapping")
        return self._pass(
            "profile.auth", "profile", "auth metadata file is a valid mapping", entry_count=len(value)
        )

    def _check_profile_environment(self) -> CheckResult:
        missing = [name for name in _REQUIRED_ENVIRONMENT if not self.environ.get(name)]
        if missing:
            return self._fail(
                "profile.environment", "profile", "required integration environment keys are missing"
            )
        return self._pass(
            "profile.environment",
            "profile",
            "required integration environment keys are present",
            required_count=len(_REQUIRED_ENVIRONMENT),
        )

    def _check_profile_credentials(self) -> CheckResult:
        configured = self.environ.get("NON_PROFIT_HERMES_CREDENTIALS_FILE")
        if not configured:
            return self._fail(
                "profile.credentials", "profile", "Google credential path is not configured"
            )
        path = Path(configured).expanduser()
        if not self.fs.is_file(path) or not self.fs.readable(path):
            return self._fail(
                "profile.credentials", "profile", "Google credential path is absent or unreadable"
            )
        return self._pass(
            "profile.credentials", "profile", "Google credential path is present and readable"
        )

    def _manifest(self) -> Mapping[str, Any] | None:
        return self._yaml_mapping(self._distribution() / "distribution.yaml")

    def _check_distribution_manifest(self) -> CheckResult:
        manifest = self._manifest()
        if manifest is None:
            return self._fail(
                "distribution.manifest", "distribution", "distribution manifest is missing or invalid"
            )
        owned = manifest.get("distribution_owned")
        if (
            manifest.get("name") != "nonprofit"
            or manifest.get("version") != _EXPECTED_VERSION
            or manifest.get("hermes_requires") != ">=0.18.2"
            or tuple(owned) != _EXPECTED_OWNED
            if isinstance(owned, list)
            else True
        ):
            return self._fail(
                "distribution.manifest",
                "distribution",
                "distribution manifest does not match the v1 contract",
                Severity.INTEGRITY,
            )
        return self._pass(
            "distribution.manifest", "distribution", "distribution manifest matches"
        )

    def _check_distribution_files(self) -> CheckResult:
        root = self._distribution()
        expected = (
            "distribution.yaml",
            "SOUL.md",
            "config.yaml",
            "skills/non-profit-hermes/SKILL.md",
            "plugins/non-profit-hermes/plugin.yaml",
            "plugins/non-profit-hermes/__init__.py",
            "plugins/non-profit-hermes/commands.py",
        )
        if any(not self.fs.is_file(root / relative) for relative in expected):
            return self._fail(
                "distribution.files",
                "distribution",
                "distribution payload files are missing",
                Severity.INTEGRITY,
            )
        return self._pass(
            "distribution.files", "distribution", "distribution payload files are present"
        )

    def _check_distribution_versions(self) -> CheckResult:
        manifest = self._manifest()
        plugin = self._yaml_mapping(
            self._distribution() / "plugins" / _UNIFIED_PLUGIN / "plugin.yaml"
        )
        try:
            skill_text = self.fs.read_text(
                self._distribution() / "skills" / _UNIFIED_PLUGIN / "SKILL.md"
            )
            skill_frontmatter = skill_text.split("---", 2)[1]
            skill = yaml.safe_load(skill_frontmatter)
        except (OSError, UnicodeError, IndexError, yaml.YAMLError):
            skill = None
        versions = (
            __version__,
            load_packaged_defaults().get("version"),
            manifest.get("version") if manifest else None,
            plugin.get("version") if plugin else None,
            skill.get("version") if isinstance(skill, Mapping) else None,
        )
        if any(version != _EXPECTED_VERSION for version in versions):
            return self._fail(
                "distribution.versions",
                "distribution",
                "package, defaults, manifest, plugin, and skill versions diverge",
                Severity.INTEGRITY,
            )
        return self._pass(
            "distribution.versions", "distribution", "all authored versions match"
        )

    def _owned_paths(self) -> tuple[Path, ...]:
        manifest = self._manifest()
        owned = manifest.get("distribution_owned") if manifest else None
        if not isinstance(owned, list) or not all(isinstance(item, str) for item in owned):
            return ()
        return tuple(self._distribution() / item for item in owned)

    def _check_privacy_inventory(self) -> CheckResult:
        owned_paths = self._owned_paths()
        if not owned_paths:
            return self._fail(
                "privacy.inventory", "privacy", "distribution-owned inventory is unavailable", Severity.INTEGRITY
            )
        for owned in owned_paths:
            candidates = (owned, *self.fs.iter_files(owned))
            for candidate in candidates:
                try:
                    relative = candidate.relative_to(self._distribution())
                except ValueError:
                    return self._fail(
                        "privacy.inventory",
                        "privacy",
                        "distribution-owned path escapes the distribution root",
                        Severity.INTEGRITY,
                    )
                lowered = {part.lower() for part in relative.parts}
                if lowered & _PRIVATE_PARTS or any(part.endswith((".db", ".log")) for part in lowered):
                    return self._fail(
                        "privacy.inventory",
                        "privacy",
                        "private runtime state appears in distribution-owned payload",
                        Severity.INTEGRITY,
                    )
        return self._pass(
            "privacy.inventory", "privacy", "distribution-owned inventory excludes private state"
        )

    def _check_privacy_literals(self) -> CheckResult:
        token_patterns = (
            re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{30,}\b"),
            re.compile(r"\bya" + r"29\.[A-Za-z0-9._-]+"),
            re.compile(r"\b1" + r"//[A-Za-z0-9._-]+"),
            re.compile(r"\bAI" + r"za[A-Za-z0-9_-]{20,}"),
            re.compile(r"\b(?:chat[_-]?id|allowed_users)\s*[:=]\s*-?\d{8,15}\b", re.IGNORECASE),
            re.compile(r"\bBearer\s+[A-Za-z0-9._-]{12,}", re.IGNORECASE),
        )
        for owned in self._owned_paths():
            for path in self.fs.iter_files(owned):
                if path.suffix.lower() not in {".py", ".yaml", ".yml", ".md", ".toml"}:
                    continue
                try:
                    content = self.fs.read_text(path)
                except (OSError, UnicodeError):
                    return self._fail(
                        "privacy.literals",
                        "privacy",
                        "distribution payload could not be scanned",
                        Severity.INTEGRITY,
                    )
                if any(pattern.search(content) for pattern in token_patterns):
                    return self._fail(
                        "privacy.literals",
                        "privacy",
                        "distribution payload contains an obvious private literal",
                        Severity.INTEGRITY,
                    )
        return self._pass(
            "privacy.literals", "privacy", "distribution payload passes private-literal scan"
        )

    def _mode_placeholders(self, mode: str) -> list[CheckResult]:
        results: list[CheckResult] = []
        for check_id, category in (
            ("gateway.live", "gateway"),
            ("telegram.live", "telegram"),
            ("google.live", "google"),
            ("public_site.live", "public-site"),
        ):
            if mode == "offline":
                results.append(self._skip(check_id, category, "offline mode: live probe intentionally skipped"))
            else:
                results.append(
                    self._warn(check_id, category, "live-readonly probe is deferred to NPH-V1-050B")
                )
        return results

    def run(self, *, mode: str = "offline", strict: bool = False) -> DoctorReport:
        if mode not in {"offline", "live-readonly"}:
            raise ValueError("mode must be offline or live-readonly")
        checks: list[tuple[str, str, Callable[[], CheckResult]]] = [
            ("distribution.files", "distribution", self._check_distribution_files),
            ("distribution.manifest", "distribution", self._check_distribution_manifest),
            ("distribution.versions", "distribution", self._check_distribution_versions),
            ("package.defaults", "package", self._check_package_defaults),
            ("package.files", "package", self._check_package_files),
            ("package.import", "package", self._check_package_import),
            ("package.source_commit", "package", self._check_source_commit),
            ("package.source_safety", "package", self._check_package_safety),
            ("package.version", "package", self._check_package_version),
            ("privacy.inventory", "privacy", self._check_privacy_inventory),
            ("privacy.literals", "privacy", self._check_privacy_literals),
            ("profile.auth", "profile", self._check_profile_auth),
            ("profile.config", "profile", self._check_profile_config),
            ("profile.credentials", "profile", self._check_profile_credentials),
            ("profile.environment", "profile", self._check_profile_environment),
            ("profile.exists", "profile", self._check_profile_exists),
            ("profile.plugin", "profile", self._check_profile_plugin),
        ]
        results: list[CheckResult] = []
        for check_id, category, check in checks:
            try:
                results.append(check())
            except Exception as error:
                results.append(
                    self._fail(
                        check_id,
                        category,
                        f"check raised {type(error).__name__}",
                        Severity.RUNTIME,
                    )
                )
        results.extend(self._mode_placeholders(mode))
        ordered = tuple(sorted(results, key=lambda result: result.id))
        highest = max((int(result.severity) for result in ordered), default=0)
        if strict and highest == int(Severity.WARNING):
            highest = int(Severity.CONFIGURATION)
        summary = {
            status.value.lower(): sum(result.status is status for result in ordered)
            for status in Status
        }
        return DoctorReport(
            mode=mode,
            profile=self.profile,
            strict=strict,
            package_version=__version__,
            checks=ordered,
            exit_code=highest,
            summary=summary,
        )


__all__ = [
    "CheckResult",
    "DoctorReport",
    "DoctorRunner",
    "Filesystem",
    "LocalFilesystem",
    "Severity",
    "Status",
    "redact",
]
