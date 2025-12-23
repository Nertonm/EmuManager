import logging
from pathlib import Path

from ..common.execution import find_tool, run_cmd

logger = logging.getLogger(__name__)

class DolphinConverter:
    """
    Handles conversion of GameCube/Wii games to RVZ using dolphin-tool.
    """
    
    def __init__(self):
        self.dolphin_tool = find_tool("dolphin-tool")
        if not self.dolphin_tool:
            # Try finding 'dolphin-emu-tool' or just 'dolphin-emu' with arguments if needed
            # On some distros it might be different.
            self.dolphin_tool = find_tool("dolphin-emu-tool")

    def check_tool(self) -> bool:
        return self.dolphin_tool is not None

    def convert_to_rvz(self, input_file: Path, output_file: Path, block_size: int = 131072, compression: str = "zstd", level: int = 5) -> bool:
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
            logger.error("dolphin-tool not found")
            return False

        # dolphin-tool convert -i <input> -o <output> -f rvz -b <block_size> -c <compression> -l <level>
        cmd = [
            str(self.dolphin_tool),
            "convert",
            "-i", str(input_file),
            "-o", str(output_file),
            "-f", "rvz",
            "-b", str(block_size),
            "-c", compression,
            "--compression_level", str(level)
        ]
        
        logger.info(f"Converting {input_file.name} to RVZ...")
        try:
            # dolphin-tool output is often noisy or minimal.
            result = run_cmd(cmd, timeout=None) # Conversion can take time
            if result.returncode == 0 and output_file.exists():
                logger.info(f"Successfully converted to {output_file}")
                return True
            else:
                logger.error(f"Conversion failed with code {result.returncode}")
                if result.stderr:
                    logger.error(f"Stderr: {result.stderr.decode('utf-8', errors='ignore')}")
                return False
        except Exception as e:
            logger.error(f"Exception during conversion: {e}")
            return False

    def verify_rvz(self, file_path: Path) -> bool:
        """
        Verifies the integrity of an RVZ/ISO file using dolphin-tool verify.
        """
        if not self.check_tool():
            logger.error("dolphin-tool not found")
            return False

        cmd = [
            str(self.dolphin_tool),
            "verify",
            "-i", str(file_path)
        ]
        
        logger.info(f"Verifying {file_path.name}...")
        try:
            result = run_cmd(cmd, timeout=None)
            # dolphin-tool verify returns 0 on success (good dump)
            if result.returncode == 0:
                logger.info(f"Verification passed for {file_path.name}")
                return True
            else:
                logger.warning(f"Verification failed for {file_path.name} (Code {result.returncode})")
                # Output might contain details
                if result.stdout:
                    logger.info(f"Output: {result.stdout.decode('utf-8', errors='ignore')}")
                return False
        except Exception as e:
            logger.error(f"Exception during verification: {e}")
            return False

    def get_metadata(self, file_path: Path) -> dict:
        """
        Extracts metadata (Game ID, Title, Revision) using dolphin-tool header.
        Returns a dict with keys: game_id, internal_name, revision.
        """
        if not self.check_tool():
            return {}

        cmd = [
            str(self.dolphin_tool),
            "header",
            "-i", str(file_path)
        ]
        
        try:
            result = run_cmd(cmd, timeout=10)
            if result.returncode != 0:
                return {}
            
            output = result.stdout.decode("utf-8", errors="ignore")
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
            logger.error(f"Error getting metadata for {file_path}: {e}")
            return {}
