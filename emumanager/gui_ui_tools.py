from __future__ import annotations


IDENTIFY_VERIFY_LABEL = "Identify & Verify Games"
ORGANIZE_LABEL = "Organize (Rename)"

TOOL_TAB_SPECS = [
    {
        "tab_attr": "tab_switch",
        "tab_title": "Switch",
        "group_title": "Nintendo Switch Actions",
        "actions": [
            {
                "attr_name": "btn_organize",
                "text": "Organize Library (Rename/Move)",
                "tooltip": "Organizes Switch ROMs based on metadata (TitleID, Version, etc)",
                "icon_name": "SP_FileDialogListView",
            },
            {
                "attr_name": "btn_health",
                "text": "Health Check (Integrity + Virus)",
                "tooltip": "Verifies NCA integrity and scans for viruses",
                "icon_name": "SP_DialogApplyButton",
            },
            {
                "attr_name": "btn_switch_compress",
                "text": "Compress Library (NSP -> NSZ)",
                "tooltip": "Compresses all NSP files in the library to NSZ format",
                "icon_name": "SP_ArrowDown",
            },
            {
                "attr_name": "btn_switch_decompress",
                "text": "Decompress Library (NSZ -> NSP)",
                "tooltip": "Decompresses all NSZ files in the library back to NSP format",
                "icon_name": "SP_ArrowUp",
            },
        ],
    },
    {
        "tab_attr": "tab_psx",
        "tab_title": "PS1",
        "group_title": "PlayStation 1 Actions",
        "actions": [
            {
                "attr_name": "btn_psx_convert",
                "text": "Convert BIN/CUE/ISO to CHD",
                "tooltip": "Converts PS1 games to CHD format to save space",
                "icon_name": "SP_DriveCDIcon",
            },
            {
                "attr_name": "btn_psx_verify",
                "text": IDENTIFY_VERIFY_LABEL,
                "tooltip": "Scans PS1 games, extracts Serials, and identifies titles",
                "icon_name": "SP_DialogApplyButton",
            },
            {
                "attr_name": "btn_psx_organize",
                "text": ORGANIZE_LABEL,
                "tooltip": "Renames PS1 games based on Serial (e.g. 'Title [Serial].chd')",
                "icon_name": "SP_FileDialogListView",
            },
        ],
    },
    {
        "tab_attr": "tab_ps2",
        "tab_title": "PS2",
        "group_title": "PlayStation 2 Actions",
        "actions": [
            {
                "attr_name": "btn_ps2_convert",
                "text": "Convert ISO/CSO to CHD",
                "tooltip": "Converts PS2 games to CHD format to save space",
                "icon_name": "SP_DriveCDIcon",
            },
            {
                "attr_name": "btn_ps2_verify",
                "text": IDENTIFY_VERIFY_LABEL,
                "tooltip": "Scans PS2 games, extracts Serials, and identifies titles",
                "icon_name": "SP_DialogApplyButton",
            },
            {
                "attr_name": "btn_ps2_organize",
                "text": ORGANIZE_LABEL,
                "tooltip": "Renames PS2 games based on Serial (e.g. 'Title [Serial].iso')",
                "icon_name": "SP_FileDialogListView",
            },
        ],
    },
    {
        "tab_attr": "tab_ps3",
        "tab_title": "PS3",
        "group_title": "PlayStation 3 Actions",
        "actions": [
            {
                "attr_name": "btn_ps3_verify",
                "text": IDENTIFY_VERIFY_LABEL,
                "tooltip": "Scans PS3 games (ISO/Folder), extracts Serials, and identifies titles",
                "icon_name": "SP_DialogApplyButton",
            },
            {
                "attr_name": "btn_ps3_organize",
                "text": ORGANIZE_LABEL,
                "tooltip": "Renames PS3 games based on Serial (e.g. 'Title [Serial]')",
                "icon_name": "SP_FileDialogListView",
            },
        ],
    },
    {
        "tab_attr": "tab_psp",
        "tab_title": "PSP",
        "group_title": "PlayStation Portable (PSP) Actions",
        "actions": [
            {
                "attr_name": "btn_psp_verify",
                "text": IDENTIFY_VERIFY_LABEL,
                "tooltip": "Scans PSP games (ISO/CSO/PBP), extracts Serials, and identifies titles",
                "icon_name": "SP_DialogApplyButton",
            },
            {
                "attr_name": "btn_psp_organize",
                "text": ORGANIZE_LABEL,
                "tooltip": "Renames PSP games based on Serial (e.g. 'Title [Serial]')",
                "icon_name": "SP_FileDialogListView",
            },
            {
                "attr_name": "btn_psp_compress",
                "text": "Compress ISO to CSO",
                "tooltip": "Compresses PSP ISO files to CSO format",
                "icon_name": "SP_ArrowDown",
            },
        ],
    },
    {
        "tab_attr": "tab_dolphin",
        "tab_title": "GameCube / Wii",
        "group_title": "Dolphin (GC/Wii) Actions",
        "actions": [
            {
                "attr_name": "btn_dolphin_organize",
                "text": "Organize Library (Rename)",
                "tooltip": "Renames GC/Wii games based on metadata (Internal Name [GameID])",
                "icon_name": "SP_FileDialogListView",
            },
            {
                "attr_name": "btn_dolphin_convert",
                "text": "Convert ISO/WBFS to RVZ",
                "tooltip": "Converts GameCube/Wii games to RVZ format (Lossless compression)",
                "icon_name": "SP_DriveCDIcon",
            },
            {
                "attr_name": "btn_dolphin_verify",
                "text": IDENTIFY_VERIFY_LABEL,
                "tooltip": "Scans GC/Wii games, extracts IDs, and verifies integrity",
                "icon_name": "SP_DialogApplyButton",
            },
        ],
    },
    {
        "tab_attr": "tab_n3ds",
        "tab_title": "Nintendo 3DS",
        "group_title": "Nintendo 3DS Actions",
        "actions": [
            {
                "attr_name": "btn_n3ds_organize",
                "text": "Organize Library",
                "tooltip": "Organizes 3DS ROMs based on metadata",
            },
            {
                "attr_name": "btn_n3ds_verify",
                "text": "Verify Library",
                "tooltip": "Verifies 3DS ROMs integrity",
            },
            {
                "attr_name": "btn_n3ds_compress",
                "text": "Compress to 7z",
                "tooltip": "Compress .3ds/.cia to .7z",
            },
            {
                "attr_name": "btn_n3ds_decompress",
                "text": "Decompress from 7z",
                "tooltip": "Decompress .7z to original format",
            },
            {
                "attr_name": "btn_n3ds_convert_cia",
                "text": "Convert 3DS to CIA",
                "tooltip": "Convert .3ds files to .cia using 3dsconv",
            },
            {
                "attr_name": "btn_n3ds_decrypt",
                "text": "Decrypt 3DS",
                "tooltip": "Decrypt .3ds files (requires ctrtool)",
            },
        ],
    },
    {
        "tab_attr": "tab_sega",
        "tab_title": "Sega",
        "group_title": "Sega Systems (Dreamcast, Saturn, MegaDrive, etc)",
        "actions": [
            {
                "attr_name": "btn_sega_convert",
                "text": "Convert CD-based to CHD",
                "tooltip": "Converts GDI/CUE/ISO to CHD (Dreamcast, Saturn, SegaCD)",
                "icon_name": "SP_DriveCDIcon",
            },
            {
                "attr_name": "btn_sega_verify",
                "text": IDENTIFY_VERIFY_LABEL,
                "tooltip": "Verify Sega games using DAT files",
                "icon_name": "SP_DialogApplyButton",
            },
            {
                "attr_name": "btn_sega_organize",
                "text": ORGANIZE_LABEL,
                "tooltip": "Rename Sega games based on DAT/Metadata",
                "icon_name": "SP_FileDialogListView",
            },
        ],
    },
    {
        "tab_attr": "tab_microsoft",
        "tab_title": "Microsoft",
        "group_title": "Microsoft Systems (Xbox, Xbox 360)",
        "actions": [
            {
                "attr_name": "btn_ms_verify",
                "text": IDENTIFY_VERIFY_LABEL,
                "tooltip": "Verify Xbox games using DAT files",
                "icon_name": "SP_DialogApplyButton",
            },
            {
                "attr_name": "btn_ms_organize",
                "text": ORGANIZE_LABEL,
                "tooltip": "Rename Xbox games based on DAT/Metadata",
                "icon_name": "SP_FileDialogListView",
            },
        ],
    },
    {
        "tab_attr": "tab_nintendo_legacy",
        "tab_title": "Nintendo (Legacy)",
        "group_title": "Nintendo Legacy (NES, SNES, N64, GBA, NDS)",
        "actions": [
            {
                "attr_name": "btn_nint_compress",
                "text": "Compress to 7z/Zip",
                "tooltip": "Compress ROMs to save space",
                "icon_name": "SP_ArrowDown",
            },
            {
                "attr_name": "btn_nint_verify",
                "text": IDENTIFY_VERIFY_LABEL,
                "tooltip": "Verify games using DAT files",
                "icon_name": "SP_DialogApplyButton",
            },
            {
                "attr_name": "btn_nint_organize",
                "text": ORGANIZE_LABEL,
                "tooltip": "Rename games based on DAT/Metadata",
                "icon_name": "SP_FileDialogListView",
            },
        ],
    },
    {
        "tab_attr": "tab_general",
        "tab_title": "General",
        "group_title": "General Maintenance",
        "actions": [
            {
                "attr_name": "btn_clean_junk",
                "text": "Clean Junk Files (.txt, .nfo, empty dirs)",
                "icon_name": "SP_TrashIcon",
            },
        ],
    },
]


class MainWindowUIToolsMixin:
    def setup_tools_tab(self, qt, parent):
        layout = qt.QVBoxLayout(parent)
        self.tools_tabs = qt.QTabWidget()
        layout.addWidget(self.tools_tabs)

        for spec in TOOL_TAB_SPECS:
            self._create_action_tab(qt, **spec)

        self._setup_quarantine_tab(qt)

    def _setup_quarantine_tab(self, qt):
        self.tab_quarantine = qt.QWidget()
        layout = qt.QVBoxLayout(self.tab_quarantine)

        self.quarantine_table = qt.QTableWidget()
        self.quarantine_table.setColumnCount(4)
        self.quarantine_table.setHorizontalHeaderLabels(
            ["Path", "Size", "MTime", "Status"]
        )
        try:
            self.quarantine_table.setEditTriggers(qt.QTableWidget.NoEditTriggers)
            self.quarantine_table.setSelectionBehavior(qt.QTableWidget.SelectRows)
            self.quarantine_table.setSelectionMode(qt.QTableWidget.SingleSelection)
        except Exception:
            pass

        layout.addWidget(self.quarantine_table)

        btn_layout = qt.QHBoxLayout()
        for attr_name, text in [
            ("btn_quar_open", "Open Location"),
            ("btn_quar_restore", "Restore"),
            ("btn_quar_delete", "Delete"),
        ]:
            btn_layout.addWidget(
                self._make_button(
                    qt,
                    text,
                    attr_name=attr_name,
                    enabled=False,
                )
            )
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.tools_tabs.addTab(self.tab_quarantine, "Quarantine")
