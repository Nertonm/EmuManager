from __future__ import annotations

import logging

from emumanager.gui_actions import ActionsDialog
from emumanager.gui_quarantine import QuarantineDialog


class ToolsDialogsMixin:
    def on_show_actions(self):
        """Open a dialog showing recent library actions."""
        try:
            qt = self.mw._qtwidgets
            dlg = ActionsDialog(qt, self.mw.window, self.mw.library_db)
            dlg.show()
        except Exception as e:
            logging.exception(f"Failed to open actions dialog: {e}")

    def on_show_quarantine(self):
        """Open a dialog showing quarantined files and allow restore/delete."""
        try:
            qt = self.mw._qtwidgets
            dlg = QuarantineDialog(qt, self.mw.window, self.mw.library_db, self.mw)
            dlg.show()
        except Exception as e:
            logging.exception(f"Failed to open quarantine dialog: {e}")

    def on_generic_verify_click(self):
        """Redirects to the Verification tab."""
        self.ui.tabs.setCurrentWidget(self.ui.tab_verification)
        logging.info("Please select a DAT file to verify your games.")
        self.ui.btn_select_dat.setFocus()

    def on_generic_organize_click(self):
        self.mw._qtwidgets.QMessageBox.information(
            self.mw.window,
            "Feature Not Available",
            "Automatic organization for this system is not yet implemented.\n"
            "Please use the 'Organize (Rename)' button in the Dashboard "
            "for generic renaming.",
        )

    def on_sega_convert(self):
        self.mw._qtwidgets.QMessageBox.information(
            self.mw.window,
            "Sega Conversion",
            "CHD conversion for Sega systems (Dreamcast/Saturn) uses the same "
            "'chdman' tool as PS1.\n"
            "This feature will be fully enabled in the next update.",
        )

    def on_nint_compress(self):
        self.mw._qtwidgets.QMessageBox.information(
            self.mw.window,
            "Compression",
            "Generic 7z/Zip compression for legacy systems is coming soon.",
        )
