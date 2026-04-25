from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from src.core.models import ApexArtifact, PmdViolation

LogCallback = Callable[[str], None]


@dataclass(slots=True)
class PmdRunResult:
    violations: list[PmdViolation]
    command_used: str = ""


class PmdService:
    DEFAULT_RULESET = "category/apex/bestpractices.xml"

    def __init__(
        self, workspace_dir: str | Path, log_callback: LogCallback | None = None
    ) -> None:
        self.workspace_dir = Path(workspace_dir).resolve()
        self.log: LogCallback = log_callback or (lambda message: None)
        self.executable = self._resolve_pmd_executable()

    def analyze_apex(
        self,
        artifacts: list[ApexArtifact],
        ruleset_path: str | Path | None = None,
    ) -> PmdRunResult:
        if not artifacts:
            return PmdRunResult(violations=[])
        if not self.executable:
            self.log("PMD non detecte dans le PATH, analyse PMD ignoree.")
            return PmdRunResult(violations=[])

        artifact_paths = {artifact.source_path.resolve() for artifact in artifacts}
        scan_dir = self._scan_directory(artifact_paths)
        ruleset = self._resolve_ruleset(ruleset_path)
        commands = [
            [self.executable, "check", "-d", str(scan_dir), "-R", ruleset, "-f", "json"],
            [self.executable, "-d", str(scan_dir), "-R", ruleset, "-f", "json"],
        ]

        last_error = ""
        for command in commands:
            completed = subprocess.run(
                command,
                cwd=self.workspace_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            output = (completed.stdout or "").strip()
            if not output:
                last_error = (completed.stderr or "").strip() or f"retour={completed.returncode}"
                continue
            parsed = self._parse_json_output(output, artifact_paths)
            if parsed is not None:
                command_str = " ".join(command)
                self.log(
                    f"PMD execute ({len(parsed)} violation(s)) via `{command_str}`."
                )
                return PmdRunResult(violations=parsed, command_used=command_str)
            last_error = "Sortie PMD non exploitable (JSON invalide)."

        if last_error:
            self.log(f"Analyse PMD ignoree: {last_error}")
        return PmdRunResult(violations=[])

    def _scan_directory(self, artifact_paths: set[Path]) -> Path:
        roots = [str(path.parent) for path in artifact_paths]
        return Path(os.path.commonpath(roots))

    def _resolve_ruleset(self, ruleset_path: str | Path | None) -> str:
        if ruleset_path is None:
            return self.DEFAULT_RULESET
        candidate = Path(ruleset_path).resolve()
        if candidate.exists():
            return str(candidate)
        return str(ruleset_path)

    def _parse_json_output(self, output: str, artifact_paths: set[Path]) -> list[PmdViolation] | None:
        try:
            payload = json.loads(output)
        except json.JSONDecodeError:
            return None

        files = payload.get("files", [])
        violations: list[PmdViolation] = []
        for file_item in files:
            filename = file_item.get("filename") or file_item.get("fileName") or ""
            if not filename:
                continue
            file_path = Path(filename).resolve()
            if file_path not in artifact_paths:
                continue
            for entry in file_item.get("violations", []):
                violations.append(
                    PmdViolation(
                        file_path=file_path,
                        rule=str(entry.get("rule") or ""),
                        ruleset=str(entry.get("ruleset") or entry.get("ruleSet") or ""),
                        priority=str(entry.get("priority") or ""),
                        begin_line=int(entry.get("beginLine") or entry.get("beginline") or 0),
                        end_line=int(entry.get("endLine") or entry.get("endline") or 0),
                        message=str(entry.get("description") or entry.get("message") or ""),
                    )
                )
        return violations

    def _resolve_pmd_executable(self) -> str:
        for candidate in ("pmd", "pmd.bat", "pmd.cmd"):
            resolved = shutil.which(candidate)
            if resolved:
                return resolved
        return ""
