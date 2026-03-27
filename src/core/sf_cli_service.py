from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import shutil
import subprocess


@dataclass(slots=True)
class OrgSummary:
    alias: str
    username: str
    display_name: str
    instance_url: str
    login_url: str
    org_id: str
    connected_status: str
    is_sandbox: bool
    is_dev_hub: bool
    tracks_source: bool

    @property
    def org_ref(self) -> str:
        return self.alias or self.username

    @property
    def display_label(self) -> str:
        org_type = "Sandbox" if self.is_sandbox else "Org"
        devhub = " / DevHub" if self.is_dev_hub else ""
        alias = self.alias or "(sans alias)"
        return f"{alias} | {self.username} | {org_type}{devhub}"


class SalesforceCliService:
    def __init__(self, workspace_dir: str | Path, log_callback=None) -> None:
        self.workspace_dir = Path(workspace_dir).resolve()
        self.log = log_callback or (lambda message: None)
        self.project_dir = self.workspace_dir / ".sf_cli_project"
        self.sf_executable = self._resolve_sf_executable()
        self._ensure_project()

    def list_orgs(self) -> list[OrgSummary]:
        payload = self._run_json([self.sf_executable, "org", "list", "--json"])
        orgs_by_key: dict[tuple[str, str], OrgSummary] = {}

        for section in ("nonScratchOrgs", "sandboxes", "scratchOrgs", "devHubs"):
            for item in payload.get(section, []):
                summary = OrgSummary(
                    alias=item.get("alias") or "",
                    username=item.get("username") or "",
                    display_name=item.get("name") or item.get("instanceName") or "",
                    instance_url=item.get("instanceUrl") or "",
                    login_url=item.get("loginUrl") or "",
                    org_id=item.get("orgId") or "",
                    connected_status=item.get("connectedStatus") or "",
                    is_sandbox=bool(item.get("isSandbox")),
                    is_dev_hub=bool(item.get("isDevHub")),
                    tracks_source=bool(item.get("tracksSource")),
                )
                orgs_by_key[(summary.alias, summary.username)] = summary

        orgs = sorted(
            orgs_by_key.values(),
            key=lambda item: ((item.alias or item.username).lower(), item.username.lower()),
        )
        self._emit_log(f"{len(orgs)} org(s) disponible(s) detectee(s).")
        return orgs

    def login_web(self, alias: str, instance_url: str = "") -> list[OrgSummary]:
        if not alias.strip():
            raise ValueError("Un alias est obligatoire pour la connexion web.")

        command = [self.sf_executable, "org", "login", "web", "--alias", alias.strip()]
        if instance_url.strip():
            command.extend(["--instance-url", instance_url.strip()])

        self._emit_log(f"Ouverture de la connexion web Salesforce pour l'alias `{alias.strip()}`.")
        self._run_streaming(command)
        self._emit_log("Connexion web terminee, actualisation de la liste des orgs.")
        return self.list_orgs()

    def generate_manifest(self, target_org: str, source_dir: str | Path) -> Path:
        source_path = Path(source_dir).resolve()
        source_path.mkdir(parents=True, exist_ok=True)
        manifest_dir = source_path / "manifest"
        manifest_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = manifest_dir / "package.xml"

        command = [
            self.sf_executable,
            "project",
            "generate",
            "manifest",
            "--from-org",
            target_org,
            "--output-dir",
            str(manifest_dir),
        ]
        self._emit_log(f"Generation du manifest pour l'org `{target_org}`.")
        self._run_streaming(command)
        if not manifest_path.exists():
            raise RuntimeError("Le manifest n'a pas ete genere au chemin attendu.")
        self._emit_log(f"Manifest genere: {manifest_path}")
        return manifest_path

    def retrieve_from_org(
        self,
        target_org: str,
        source_dir: str | Path,
        manifest_path: str | Path | None = None,
    ) -> Path:
        source_path = Path(source_dir).resolve()
        source_path.mkdir(parents=True, exist_ok=True)

        effective_manifest = (
            Path(manifest_path).resolve()
            if manifest_path is not None
            else source_path / "manifest" / "package.xml"
        )
        if not effective_manifest.exists():
            raise FileNotFoundError(f"Manifest introuvable: {effective_manifest}")

        project_root = self._ensure_retrieve_project(source_path)
        command = [
            self.sf_executable,
            "project",
            "retrieve",
            "start",
            "--target-org",
            target_org,
            "--manifest",
            str(effective_manifest.relative_to(project_root)),
            "--wait",
            "33",
        ]
        self._emit_log(f"Debut du retrieve depuis l'org `{target_org}` vers `{source_path}`.")
        self._run_streaming(command, cwd=project_root)
        self._emit_log(f"Retrieve termine dans {source_path}")
        return source_path

    def _ensure_project(self) -> None:
        self.project_dir.mkdir(parents=True, exist_ok=True)
        package_dir = self.project_dir / "force-app"
        package_dir.mkdir(parents=True, exist_ok=True)

        project_config = self.project_dir / "sfdx-project.json"
        if not project_config.exists():
            project_config.write_text(
                json.dumps(
                    {
                        "packageDirectories": [{"path": "force-app", "default": True}],
                        "name": "html-doc-generator-cli",
                        "namespace": "",
                        "sfdcLoginUrl": "https://login.salesforce.com",
                        "sourceApiVersion": "65.0",
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

    def _ensure_retrieve_project(self, source_path: Path) -> Path:
        source_path.mkdir(parents=True, exist_ok=True)
        package_dir = source_path / "force-app" / "main" / "default"
        package_dir.mkdir(parents=True, exist_ok=True)

        project_config = source_path / "sfdx-project.json"
        if not project_config.exists():
            project_config.write_text(
                json.dumps(
                    {
                        "packageDirectories": [{"path": "force-app", "default": True}],
                        "name": "html-doc-generator-retrieve",
                        "namespace": "",
                        "sfdcLoginUrl": "https://login.salesforce.com",
                        "sourceApiVersion": "65.0",
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        return source_path

    def _resolve_sf_executable(self) -> str:
        for candidate in ("sf", "sf.cmd"):
            resolved = shutil.which(candidate)
            if resolved:
                return resolved

        common_paths = [
            Path(r"C:\Program Files\sf\bin\sf.cmd"),
            Path(r"C:\Program Files\sf\client\bin\sf.cmd"),
            Path.home() / "AppData" / "Local" / "sf" / "client" / "bin" / "sf.cmd",
        ]
        for candidate in common_paths:
            if candidate.exists():
                return str(candidate)

        raise FileNotFoundError("Salesforce CLI est introuvable. Installez `sf` ou ajoutez-le au PATH.")

    def _emit_log(self, message: str) -> None:
        try:
            self.log(message)
        except UnicodeEncodeError:
            self.log(message.encode("ascii", errors="replace").decode("ascii"))

    def _run_json(self, command: list[str]) -> dict:
        completed = subprocess.run(
            command,
            cwd=self.project_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "Commande Salesforce CLI en echec.")

        payload = json.loads(completed.stdout)
        if payload.get("status", 0) != 0:
            message = payload.get("message") or completed.stderr.strip() or "Commande Salesforce CLI en echec."
            raise RuntimeError(message)
        return payload.get("result", {})

    def _run_streaming(self, command: list[str], cwd: Path | None = None) -> None:
        process = subprocess.Popen(
            command,
            cwd=(cwd or self.project_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        assert process.stdout is not None
        for line in process.stdout:
            stripped = line.rstrip()
            if stripped:
                self._emit_log(stripped)

        return_code = process.wait()
        if return_code != 0:
            raise RuntimeError(f"La commande Salesforce CLI a echoue ({return_code}).")
