from __future__ import annotations

import logging

from emumanager.gui_messages import MSG_SELECT_BASE


class MainWindowVerificationDatsMixin:
    def _download_dats_phase(self, downloader):
        self.progress_hook(0.0, "Fetching No-Intro file list...")
        ni_files = downloader.list_available_dats("no-intro")

        self.progress_hook(0.0, "Fetching Redump file list...")
        rd_files = downloader.list_available_dats("redump")

        return ni_files, rd_files

    def _execute_dat_downloads(self, downloader, ni_files, rd_files):
        import concurrent.futures

        total_files = len(ni_files) + len(rd_files)
        if total_files == 0:
            return "No DAT files found to download."

        self.log_msg(
            f"Found {len(ni_files)} No-Intro and {len(rd_files)} Redump DATs. Starting..."
        )
        completed = success = 0

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for filename in ni_files:
                futures.append(executor.submit(downloader.download_dat, "no-intro", filename))
            for filename in rd_files:
                futures.append(executor.submit(downloader.download_dat, "redump", filename))

            for future in concurrent.futures.as_completed(futures):
                completed += 1
                try:
                    if future.result():
                        success += 1
                except Exception as e:
                    logging.debug(f"DAT download failed: {e}")

                percent = completed / total_files
                self.progress_hook(
                    percent,
                    f"Downloading: {completed}/{total_files} ({(percent * 100):.1f}%)",
                )

        return f"Update complete. Downloaded {success}/{total_files} DATs."

    def on_update_dats(self):
        if not self._last_base:
            self.log_msg(MSG_SELECT_BASE)
            return

        dats_dir = self._last_base / "dats"
        dats_dir.mkdir(parents=True, exist_ok=True)

        self.log_msg("Initializing DAT update process...")
        self.progress_hook(0.0, "Connecting to GitHub...")
        self._set_ui_enabled(False)

        def _work():
            downloader = self._create_dat_downloader(dats_dir)
            ni_files, rd_files = self._download_dats_phase(downloader)
            return self._execute_dat_downloads(downloader, ni_files, rd_files)

        def _done(res):
            self.log_msg(str(res))
            self._set_ui_enabled(True)
            self.progress_hook(1.0, "DAT update complete")

        self._run_in_background(_work, _done)
