from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from src.core.models import SecurityArtifact


class ExcelReportWriter:
    def __init__(self, log_callback=None) -> None:
        self.log = log_callback or (lambda message: None)

    def write_security_workbook(
        self, artifacts: list[SecurityArtifact], output_path: str | Path, title: str
    ) -> Path:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        workbook = Workbook()
        summary = workbook.active
        summary.title = "Synthese"
        self._write_sheet(
            summary,
            [
                "Nom",
                "Label",
                "Description",
                "Nb droits objet",
                "Nb droits champ",
                "Nb permissions systeme",
                "Nb applis",
                "Nb onglets",
                "Nb classes",
                "Nb flows",
            ],
            [
                [
                    artifact.name,
                    artifact.label,
                    artifact.description,
                    len(artifact.object_permissions),
                    len(artifact.field_permissions),
                    len(artifact.user_permissions),
                    len(artifact.application_visibilities),
                    len(artifact.tab_visibilities),
                    len(artifact.class_accesses),
                    len(artifact.flow_accesses),
                ]
                for artifact in artifacts
            ],
        )

        self._write_sheet(
            workbook.create_sheet("DroitsObjet"),
            ["Nom", "Objet", "Lecture", "Creation", "Modification", "Suppression", "ViewAll", "ModifyAll"],
            [
                [
                    artifact.name,
                    permission.object_name,
                    permission.allow_read,
                    permission.allow_create,
                    permission.allow_edit,
                    permission.allow_delete,
                    permission.view_all_records,
                    permission.modify_all_records,
                ]
                for artifact in artifacts
                for permission in artifact.object_permissions
            ],
        )

        self._write_sheet(
            workbook.create_sheet("DroitsChamp"),
            ["Nom", "Champ", "Lecture", "Modification"],
            [
                [artifact.name, permission.field_name, permission.readable, permission.editable]
                for artifact in artifacts
                for permission in artifact.field_permissions
            ],
        )

        self._write_sheet(
            workbook.create_sheet("PermissionsSysteme"),
            ["Nom", "Permission", "Activee"],
            [
                [artifact.name, permission.name, permission.enabled]
                for artifact in artifacts
                for permission in artifact.user_permissions
            ],
        )

        self._write_sheet(
            workbook.create_sheet("Applications"),
            ["Nom", "Application", "Visible", "Defaut"],
            [
                [artifact.name, app.name, app.visible, app.default]
                for artifact in artifacts
                for app in artifact.application_visibilities
            ],
        )

        self._write_sheet(
            workbook.create_sheet("Onglets"),
            ["Nom", "Onglet", "Visibilite", "Defaut"],
            [
                [artifact.name, tab.name, tab.visible, tab.default]
                for artifact in artifacts
                for tab in artifact.tab_visibilities
            ],
        )

        self._write_sheet(
            workbook.create_sheet("ClassesApex"),
            ["Nom", "Classe Apex", "Active"],
            [
                [artifact.name, access.name, access.enabled]
                for artifact in artifacts
                for access in artifact.class_accesses
            ],
        )

        self._write_sheet(
            workbook.create_sheet("Flows"),
            ["Nom", "Flow", "Actif"],
            [
                [artifact.name, access.name, access.enabled]
                for artifact in artifacts
                for access in artifact.flow_accesses
            ],
        )

        self._write_sheet(
            workbook.create_sheet("RecordTypes"),
            ["Nom", "Record Type", "Visible", "Defaut"],
            [
                [artifact.name, item.record_type, item.visible, item.default]
                for artifact in artifacts
                for item in artifact.record_type_visibilities
            ],
        )

        self._write_sheet(
            workbook.create_sheet("CustomPermissions"),
            ["Nom", "Custom Permission", "Activee"],
            [
                [artifact.name, access.name, access.enabled]
                for artifact in artifacts
                for access in artifact.custom_permissions
            ],
        )

        workbook.save(output)
        self.log(f"{title} genere: {output}")
        return output

    def write_inventory_workbook(
        self, inventory: dict[str, list[dict[str, object]]], output_path: str | Path
    ) -> Path:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        workbook = Workbook()
        sheet_definitions = [
            ("RecordTypes", "record_types"),
            ("Layouts", "layouts"),
            ("LightningPages", "lightning_pages"),
            ("ValidationRules", "validation_rules"),
            ("OmniStudio", "omnistudio"),
            ("BusinessRules", "business_rules_engine"),
            ("Flows", "flows"),
            ("PermissionSets", "permission_sets"),
            ("Profiles", "profiles"),
            ("Reports", "reports"),
            ("Dashboards", "dashboards"),
        ]

        first_title, first_key = sheet_definitions[0]
        first_rows = inventory.get(first_key, [])
        summary = workbook.active
        summary.title = first_title
        self._write_dict_sheet(summary, first_rows)

        for title, key in sheet_definitions[1:]:
            self._write_dict_sheet(workbook.create_sheet(title), inventory.get(key, []))

        workbook.save(output)
        self.log(f"Classeur inventaire metadata genere: {output}")
        return output

    def _write_sheet(self, worksheet, headers: list[str], rows: list[list[object]]) -> None:
        worksheet.append(headers)
        header_fill = PatternFill(fill_type="solid", fgColor="DCE6F1")
        for cell in worksheet[1]:
            cell.font = Font(bold=True)
            cell.fill = header_fill

        for row in rows:
            worksheet.append(row)

        worksheet.freeze_panes = "A2"
        worksheet.auto_filter.ref = worksheet.dimensions

        for index, header in enumerate(headers, start=1):
            max_length = len(header)
            for row in worksheet.iter_rows(min_col=index, max_col=index, min_row=2):
                value = row[0].value
                if value is not None:
                    max_length = max(max_length, len(str(value)))
            worksheet.column_dimensions[get_column_letter(index)].width = min(max_length + 2, 60)

    def _write_dict_sheet(self, worksheet, rows: list[dict[str, object]]) -> None:
        if rows:
            headers = list(rows[0].keys())
            data = [[row.get(header, "") for header in headers] for row in rows]
        else:
            headers = ["Information"]
            data = [["Aucune donnee trouvee"]]
        self._write_sheet(worksheet, headers, data)
