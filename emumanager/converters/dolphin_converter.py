import logging
from pathlib import Path
import shutil

from ..common.execution import find_tool, run_cmd

logger = logging.getLogger(__name__)


class DolphinConverter:
    """
    Handles conversion of GameCube/Wii games to RVZ using dolphin-tool.
    """

    def __init__(self, logger=None):
        self.use_flatpak = False
        self.logger = logger or logging.getLogger(__name__)
        self.dolphin_tool = find_tool("dolphin-tool")
        if not self.dolphin_tool:
            # Try finding 'dolphin-emu-tool'
            self.dolphin_tool = find_tool("dolphin-emu-tool")
        
        if not self.dolphin_tool:
            self._check_flatpak()

    def _check_flatpak(self):
        # Use shutil.which directly to avoid resolving symlinks (important for distrobox shims)
        flatpak_path = shutil.which("flatpak")
        if not flatpak_path:
            return

        flatpak = Path(flatpak_path)

        # Check if org.DolphinEmu.dolphin-emu is installed
        try:
            # We use run_cmd to check, but we need to be careful about imports
            # if run_cmd is not available. It is imported at top level.
            res = run_cmd(
                [str(flatpak), "info", "org.DolphinEmu.dolphin-emu"], timeout=5
            )
            if res.returncode == 0:
                self.use_flatpak = True
                self.dolphin_tool = flatpak
                self.logger.info("Using Dolphin via Flatpak")
            else:
                self.logger.debug(f"Flatpak check failed: {res.returncode}")
        except Exception as e:
            self.logger.error(f"Flatpak check exception: {e}")

    def check_tool(self) -> bool:
        return self.dolphin_tool is not None

    def _get_base_cmd(self, paths: list[Path] = None) -> list[str]:
        if self.use_flatpak:
            cmd = [str(self.dolphin_tool), "run", "--command=dolphin-tool"]
            if paths:
                for p in set(paths):
                    cmd.append(f"--filesystem={p.resolve()}")
            cmd.append("org.DolphinEmu.dolphin-emu")
            return cmd
        return [str(self.dolphin_tool)]

    def convert_to_rvz(
        self,
        input_file: Path,
        output_file: Path,
        block_size: int = 131072,
        compression: str = "zstd",
        level: int = 5,
    ) -> bool:
        """
        Converts an ISO/GCM/WBFS file to RVZ.

        Args:
            input_file: Path to source file
            output_file: Path to destination .rvz file
            block_size: Block size (default 128KB)
            compression: Compression format (zstd, lzma, none)
            level: Compression level (1-22 for zstd)
        """
        if not self.check_tool():
            self.logger.error("dolphin-tool not found")
            return False

        # dolphin-tool convert -i <input> -o <output> -f rvz -b <block> -c <comp>
        cmd = self._get_base_cmd([input_file.parent, output_file.parent]) + [
            "convert",
            "-i",
            str(input_file),
            "-o",
            str(output_file),
            "-f",
            "rvz",
            "-b",
            str(block_size),
            "-c",
            compression,
            "--compression_level",
            str(level),
        ]

        self.logger.info(f"Converting {input_file.name} to RVZ...")
        self.logger.info(f"Command: {cmd}")
        try:
            # dolphin-tool output is often noisy or minimal.
            result = run_cmd(cmd, timeout=None)  # Conversion can take time
            if result.returncode == 0 and output_file.exists():
                self.logger.info(f"Successfully converted to {output_file}")
                return True
            else:
                self.logger.error(f"Conversion failed with code {result.returncode}")
                if result.stderr:
                    # result.stderr is already a string because run_cmd uses text=True
                    self.logger.error(f"Stderr: {result.stderr}")
                return False
        except Exception as e:
            self.logger.error(f"Exception during conversion: {e}")
            return False

    def convert_to_iso(self, input_file: Path, output_file: Path) -> bool:
        """
        Converts an RVZ/GCZ/WBFS file back to ISO.

        Args:
            input_file: Path to source file
            output_file: Path to destination .iso file
        """
        if not self.check_tool():
            self.logger.error("dolphin-tool not found")
            return False

        # dolphin-tool convert -i <input> -o <output> -f iso
        cmd = self._get_base_cmd([input_file.parent, output_file.parent]) + [
            "convert",
            "-i",
            str(input_file),
            "-o",
            str(output_file),
            "-f",
            "iso",
        ]

        self.logger.info(f"Converting {input_file.name} to ISO...")
        self.logger.info(f"Command: {cmd}")
        try:
            result = run_cmd(cmd, timeout=None)
            if result.returncode == 0 and output_file.exists():
                self.logger.info(f"Successfully converted to {output_file}")
                return True
            else:
                self.logger.error(f"Conversion failed with code {result.returncode}")
                if result.stderr:
                    # result.stderr is already a string because run_cmd uses text=True
                    self.logger.error(f"Stderr: {result.stderr}")
                return False
        except Exception as e:
            self.logger.error(f"Exception during conversion: {e}")
            return False

    def verify_rvz(self, file_path: Path) -> bool:
        """
        Verifies the integrity of an RVZ/ISO file using dolphin-tool verify.
        """
        if not self.check_tool():
            self.logger.error("dolphin-tool not found")
            return False

        cmd = self._get_base_cmd([file_path.parent]) + ["verify", "-i", str(file_path)]

        self.logger.info(f"Verifying {file_path.name}...")
        try:
            result = run_cmd(cmd, timeout=None)
            # dolphin-tool verify returns 0 on success (good dump)
            if result.returncode == 0:
                self.logger.info(f"Verification passed for {file_path.name}")
                return True
            else:
                self.logger.warning(
                    f"Verification failed for {file_path.name} "
                    f"(Code {result.returncode})"
                )
                # Output might contain details
                if result.stdout:
                    self.logger.info(
                        f"Output: {result.stdout}"
                    )
                return False
        except Exception as e:
            self.logger.error(f"Exception during verification: {e}")
            return False

    def get_metadata(self, file_path: Path) -> dict:
        """
        Extracts metadata (Game ID, Title, Revision) using dolphin-tool header.
        Returns a dict with keys: game_id, internal_name, revision.
        """
        if not self.check_tool():
            return {}

        cmd = self._get_base_cmd([file_path.parent]) + ["header", "-i", str(file_path)]

        try:
            result = run_cmd(cmd, timeout=10)
            if result.returncode != 0:
                return {}

            output = result.stdout
            meta = {}
            for line in output.splitlines():
                if ":" in line:
                    key, val = line.split(":", 1)
                    key = key.strip().lower()
                    val = val.strip()
                    if key == "game id":
                        meta["game_id"] = val
                    elif key == "internal name":
                        meta["internal_name"] = val
                    elif key == "revision":
                        meta["revision"] = val
            return meta
        except Exception as e:
            self.logger.error(f"Error getting metadata for {file_path}: {e}")
            return {}
