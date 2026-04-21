from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from emumanager.switch import meta_extractor


NSZ_EXTENSIONS = {".nsz", ".xcz"}
NSZ_LEVEL_PATTERNS = [
    r"zstd(?: compression)? level\s*(?:[:=\-]\s*)?(\d+)",
    r"compression level\s*(?:[:=\-]\s*)?(\d+)",
    r"level\s*(?:[:=\-]\s*)?(\d+)",
]


def _build_logged_runner(run_cmd_fn, roms_dir: Path, filepath: Path, suffix: str, cmd_timeout):
    filebase = Path(roms_dir) / "logs" / "nsz" / f"{filepath.stem}.{suffix}"

    def _runner(cmd, **kwargs):
        return run_cmd_fn(
            cmd,
            filebase=filebase,
            timeout=cmd_timeout,
            check=kwargs.get("check", False),
        )

    return _runner


def get_metadata_impl(
    filepath,
    *,
    tool_metadata,
    is_nstool,
    keys_path,
    roms_dir,
    cmd_timeout,
    tool_nsz,
    run_cmd_fn,
    parse_tool_output_fn,
    parse_languages_fn,
    detect_languages_from_filename_fn,
    determine_type_fn,
):
    return meta_extractor.get_metadata_info(
        filepath,
        run_cmd=run_cmd_fn,
        tool_metadata=tool_metadata,
        is_nstool=is_nstool,
        keys_path=keys_path,
        tool_nsz=tool_nsz,
        roms_dir=roms_dir,
        cmd_timeout=cmd_timeout,
        parse_tool_output=parse_tool_output_fn,
        parse_languages=parse_languages_fn,
        detect_languages_from_filename=detect_languages_from_filename_fn,
        determine_type=determine_type_fn,
    )


def _verify_nsz_pass_impl(filepath, *, tool_nsz, roms_dir, cmd_timeout, run_cmd_fn, logger):
    from emumanager.switch.verify import verify_nsz

    try:
        runner = _build_logged_runner(run_cmd_fn, roms_dir, filepath, "verify_nsz", cmd_timeout)
        res = runner([str(tool_nsz), "--verify", str(filepath)])
        ok = verify_nsz(filepath, lambda *a, **k: res, tool_nsz=str(tool_nsz))
        out = (getattr(res, "stdout", "") or "") + "\n" + (getattr(res, "stderr", "") or "")
        return ok, out
    except Exception as e:
        logger.debug("nsz verify pass failed for %s: %s", filepath, e)
        return False, str(e)


def _verify_metadata_pass_impl(
    filepath,
    *,
    tool_metadata,
    is_nstool,
    keys_path,
    roms_dir,
    cmd_timeout,
    run_cmd_fn,
    logger,
):
    from emumanager.switch.verify import verify_metadata_tool

    try:
        cmd = [str(tool_metadata), "--verify", str(filepath)]
        if not is_nstool:
            cmd.insert(1, "-k")
            cmd.insert(2, str(keys_path))
        runner = _build_logged_runner(run_cmd_fn, roms_dir, filepath, "verify_meta", cmd_timeout)
        res = runner(cmd)
        ok = verify_metadata_tool(
            filepath,
            lambda *a, **k: res,
            tool_metadata=str(tool_metadata),
            is_nstool=is_nstool,
            keys_path=keys_path,
        )
        out = (getattr(res, "stdout", "") or "") + "\n" + (getattr(res, "stderr", "") or "")
        return ok, out
    except Exception as e:
        logger.debug("metadata verify pass failed for %s: %s", filepath, e)
        return False, str(e)


def _verify_hactool_deep_pass_impl(
    filepath,
    *,
    tool_hactool,
    keys_path,
    roms_dir,
    cmd_timeout,
    run_cmd_fn,
    logger,
):
    from emumanager.switch.verify import verify_hactool_deep

    try:
        if keys_path and keys_path.exists():
            cmd = [str(tool_hactool), "-k", str(keys_path), str(filepath)]
        else:
            cmd = [str(tool_hactool), str(filepath)]
        runner = _build_logged_runner(run_cmd_fn, roms_dir, filepath, "verify_hactool", cmd_timeout)
        res = runner(cmd)
        ok = verify_hactool_deep(filepath, lambda *a, **k: res, keys_path=keys_path)
        out = (getattr(res, "stdout", "") or "") + "\n" + (getattr(res, "stderr", "") or "")
        return ok, out
    except Exception as e:
        logger.debug("hactool deep verify pass failed for %s: %s", filepath, e)
        return False, str(e)


def verify_integrity_impl(
    filepath,
    *,
    deep=False,
    return_output=False,
    tool_nsz,
    roms_dir,
    cmd_timeout,
    tool_metadata,
    is_nstool,
    keys_path,
    tool_hactool,
    run_cmd_fn,
    logger,
):
    results = []
    is_nsz = filepath.suffix.lower() in NSZ_EXTENSIONS

    if is_nsz and tool_nsz:
        results.append(
            _verify_nsz_pass_impl(
                filepath,
                tool_nsz=tool_nsz,
                roms_dir=roms_dir,
                cmd_timeout=cmd_timeout,
                run_cmd_fn=run_cmd_fn,
                logger=logger,
            )
        )

    if tool_metadata:
        results.append(
            _verify_metadata_pass_impl(
                filepath,
                tool_metadata=tool_metadata,
                is_nstool=is_nstool,
                keys_path=keys_path,
                roms_dir=roms_dir,
                cmd_timeout=cmd_timeout,
                run_cmd_fn=run_cmd_fn,
                logger=logger,
            )
        )

    if deep and tool_hactool:
        results.append(
            _verify_hactool_deep_pass_impl(
                filepath,
                tool_hactool=tool_hactool,
                keys_path=keys_path,
                roms_dir=roms_dir,
                cmd_timeout=cmd_timeout,
                run_cmd_fn=run_cmd_fn,
                logger=logger,
            )
        )

    any_ok = any(ok for ok, _ in results)
    combined_out = "\n---\n".join(out for _, out in results)

    if return_output:
        return any_ok, combined_out

    if not any_ok:
        logger.debug("verify_integrity outputs:\n%s", combined_out)
        return False
    return True


def scan_for_virus_impl(
    filepath,
    *,
    tool_clamscan,
    tool_clamdscan,
    roms_dir,
    cmd_timeout,
    run_cmd_fn,
    logger,
):
    tool = tool_clamscan or tool_clamdscan
    if not tool:
        return None, "No AV scanner found"

    cmd = [str(tool), "--no-summary", str(filepath)]
    try:
        runner = _build_logged_runner(run_cmd_fn, roms_dir, filepath, "av", cmd_timeout)
        res = runner(cmd)
        out = (getattr(res, "stdout", "") or "") + "\n" + (getattr(res, "stderr", "") or "")
        rc = getattr(res, "returncode", None)
        if rc == 0:
            return False, out
        if rc == 1:
            return True, out
        logger.debug("AV scan returned code %s for %s", rc, filepath)
        return None, out
    except Exception as e:
        logger.exception("scan_for_virus failed for %s", filepath)
        return None, str(e)


def _run_nsz_info_attempts_impl(filepath, *, tool_nsz, roms_dir, cmd_timeout, run_cmd_fn, logger):
    attempts = [
        [str(tool_nsz), "--info", str(filepath)],
        [str(tool_nsz), "-i", str(filepath)],
        [str(tool_nsz), "info", str(filepath)],
    ]
    for cmd in attempts:
        try:
            runner = _build_logged_runner(run_cmd_fn, roms_dir, filepath, "info", cmd_timeout)
            res = runner(cmd)
            out = (getattr(res, "stdout", "") or "") + "\n" + (getattr(res, "stderr", "") or "")
            if out and out.strip():
                return out
        except Exception as e:
            logger.debug("nsz info attempt failed: %s", e)
            continue
    return ""


def detect_nsz_level_impl(filepath, *, tool_nsz, roms_dir, cmd_timeout, run_cmd_fn, logger) -> Optional[int]:
    if not tool_nsz:
        return None

    try:
        out = _run_nsz_info_attempts_impl(
            filepath,
            tool_nsz=tool_nsz,
            roms_dir=roms_dir,
            cmd_timeout=cmd_timeout,
            run_cmd_fn=run_cmd_fn,
            logger=logger,
        )
        if not out:
            return None

        for pattern in NSZ_LEVEL_PATTERNS:
            match = re.search(pattern, out, re.IGNORECASE)
            if match:
                return int(match.group(1))
    except Exception as e:
        logger.debug("detect_nsz_level failed for %s: %s", filepath, e)
    return None


def _should_recompress(filepath, args, *, tool_nsz, roms_dir, cmd_timeout, detect_nsz_level_fn, logger):
    if getattr(args, "recompress", False):
        return True

    try:
        cur = detect_nsz_level_fn(
            filepath,
            tool_nsz=tool_nsz,
            roms_dir=roms_dir,
            cmd_timeout=cmd_timeout,
        )
        if cur is not None and args.level > cur:
            logger.info("Detected existing zstd level %s -> will recompress to %s", cur, args.level)
            return True
    except Exception as e:
        logger.debug("Failed to detect existing nsz level for %s: %s", filepath, e)
    return False


def _move_to_quarantine(path, *, args, roms_dir, shutil_module, logger):
    try:
        qdir = args.quarantine_dir or (roms_dir / "_QUARANTINE")
        quarantine_dir = Path(qdir).resolve()
        quarantine_dir.mkdir(parents=True, exist_ok=True)
        dest = quarantine_dir / path.name
        shutil_module.move(str(path), str(dest))
        logger.info("Moved failed compressed artifact to quarantine: %s", dest)
    except Exception as e:
        logger.exception("Failed moving failed compressed artifact to quarantine: %s (%s)", path, e)


def _post_compression_cleanup(
    filepath,
    compressed_candidate,
    *,
    args,
    tool_nsz,
    roms_dir,
    cmd_timeout,
    tool_metadata,
    is_nstool,
    keys_path,
    tool_hactool,
    verify_integrity_fn,
    shutil_module,
    logger,
):
    if not (args.rm_originals and not args.dry_run and compressed_candidate):
        return

    try:
        if not (compressed_candidate.exists() and compressed_candidate.stat().st_size > 0):
            return

        ok = verify_integrity_fn(
            compressed_candidate,
            deep=False,
            tool_nsz=tool_nsz,
            roms_dir=roms_dir,
            cmd_timeout=cmd_timeout,
            tool_metadata=tool_metadata,
            is_nstool=is_nstool,
            keys_path=keys_path,
            tool_hactool=tool_hactool,
        )
        if ok:
            filepath.unlink()
            logger.info("Original removido após compressão bem-sucedida: %s", filepath.name)
        else:
            logger.warning("Compressed file generated but failed verification: %s", compressed_candidate)
            if getattr(args, "keep_on_failure", False):
                _move_to_quarantine(
                    compressed_candidate,
                    args=args,
                    roms_dir=roms_dir,
                    shutil_module=shutil_module,
                    logger=logger,
                )
    except Exception as e:
        logger.exception("Error while validating/removing original for %s: %s", filepath, e)


def _execute_recompression(
    filepath,
    *,
    args,
    tool_nsz,
    roms_dir,
    cmd_timeout,
    tool_metadata,
    is_nstool,
    keys_path,
    tool_hactool,
    run_cmd_fn,
    logger,
    col,
    tempfile_module,
    verify_integrity_fn,
):
    from emumanager.switch.compression import handle_produced_file, try_multiple_recompress_attempts

    try:
        print("   🗜️  Recomprimindo (ajuste de nível)...", end="", flush=True)
        with tempfile_module.TemporaryDirectory(prefix="nsz_recomp_") as td:
            tmpdir = Path(td)
            attempts = [
                [str(tool_nsz), "-C", "-l", str(args.level), "-o", str(tmpdir), str(filepath)],
                [str(tool_nsz), "-C", "-l", str(args.level), str(filepath), "-o", str(tmpdir)],
                [str(tool_nsz), "-C", "-l", str(args.level), str(filepath)],
            ]

            runner = _build_logged_runner(run_cmd_fn, roms_dir, filepath, "recomp", cmd_timeout)
            produced = try_multiple_recompress_attempts(
                tmpdir,
                attempts,
                runner,
                progress_callback=getattr(args, "progress_callback", None),
            )

            if produced:
                def verify_fn(path, _rc):
                    return verify_integrity_fn(
                        path,
                        deep=False,
                        tool_nsz=tool_nsz,
                        roms_dir=roms_dir,
                        cmd_timeout=cmd_timeout,
                        tool_metadata=tool_metadata,
                        is_nstool=is_nstool,
                        keys_path=keys_path,
                        tool_hactool=tool_hactool,
                    )

                result_path = handle_produced_file(
                    produced[0],
                    filepath,
                    runner,
                    verify_fn=verify_fn,
                    args=args,
                    roms_dir=roms_dir,
                )
                if result_path == filepath:
                    print(f" {col.GREEN}[OK]{col.RESET}")
                    logger.info("Recompression succeeded and file replaced: %s", filepath.name)
                return result_path

        print(f" {col.RED}[FALHA]{col.RESET}")
    except Exception as e:
        logger.exception("recompress failed for %s: %s", filepath, e)
        print(f" {col.RED}[FALHA]{col.RESET}")
    return filepath


def _handle_new_compression(
    filepath,
    *,
    args,
    tool_nsz,
    roms_dir,
    cmd_timeout,
    tool_metadata,
    is_nstool,
    keys_path,
    tool_hactool,
    run_cmd_fn,
    logger,
    col,
    verify_integrity_fn,
    shutil_module,
):
    if args.dry_run:
        return filepath.with_suffix(".nsz")

    try:
        print("   🗜️  Comprimindo...", end="", flush=True)
        from emumanager.switch.compression import compress_file

        runner = _build_logged_runner(run_cmd_fn, roms_dir, filepath, "compress", cmd_timeout)
        compressed_candidate = compress_file(
            filepath,
            runner,
            tool_nsz=str(tool_nsz),
            level=args.level,
            args=args,
            roms_dir=Path(roms_dir),
        )
        if not compressed_candidate:
            print(f" {col.RED}[FALHA]{col.RESET}")
            return filepath

        print(f" {col.GREEN}[OK]{col.RESET}")
        _post_compression_cleanup(
            filepath,
            compressed_candidate,
            args=args,
            tool_nsz=tool_nsz,
            roms_dir=roms_dir,
            cmd_timeout=cmd_timeout,
            tool_metadata=tool_metadata,
            is_nstool=is_nstool,
            keys_path=keys_path,
            tool_hactool=tool_hactool,
            verify_integrity_fn=verify_integrity_fn,
            shutil_module=shutil_module,
            logger=logger,
        )
        return compressed_candidate
    except Exception as e:
        logger.exception("compress failed for %s: %s", filepath, e)
        print(f" {col.RED}[FALHA]{col.RESET}")
        return filepath


def _handle_decompression(
    filepath,
    *,
    args,
    tool_nsz,
    roms_dir,
    cmd_timeout,
    tool_metadata,
    is_nstool,
    keys_path,
    run_cmd_fn,
    logger,
    col,
):
    if args.dry_run:
        return filepath.with_suffix(".nsp")

    try:
        print("   📦 Descomprimindo...", end="", flush=True)
        from emumanager.switch.compression import decompress_and_find_candidate

        runner = _build_logged_runner(run_cmd_fn, roms_dir, filepath, "decomp_act", cmd_timeout)
        candidate = decompress_and_find_candidate(
            filepath,
            runner,
            tool_nsz=str(tool_nsz),
            tool_metadata=str(tool_metadata) if tool_metadata else None,
            is_nstool=is_nstool,
            keys_path=keys_path,
            args=args,
            roms_dir=roms_dir,
        )
        if candidate:
            print(f" {col.GREEN}[OK]{col.RESET}")
            return candidate

        print(f" {col.RED}[FALHA]{col.RESET}")
        return filepath
    except Exception as e:
        logger.exception("decompress failed for %s: %s", filepath, e)
        print(f" {col.RED}[FALHA]{col.RESET}")
        return filepath


def handle_compression_impl(
    filepath,
    *,
    args,
    tool_nsz,
    roms_dir,
    tool_metadata,
    is_nstool,
    keys_path,
    cmd_timeout,
    tool_hactool,
    run_cmd_fn,
    logger,
    col,
    tempfile_module,
    shutil_module,
    verify_integrity_fn,
    detect_nsz_level_fn,
):
    if args.compress and filepath.suffix.lower() in NSZ_EXTENSIONS:
        if _should_recompress(
            filepath,
            args,
            tool_nsz=tool_nsz,
            roms_dir=roms_dir,
            cmd_timeout=cmd_timeout,
            detect_nsz_level_fn=detect_nsz_level_fn,
            logger=logger,
        ):
            if args.dry_run:
                return filepath
            return _execute_recompression(
                filepath,
                args=args,
                tool_nsz=tool_nsz,
                roms_dir=roms_dir,
                cmd_timeout=cmd_timeout,
                tool_metadata=tool_metadata,
                is_nstool=is_nstool,
                keys_path=keys_path,
                tool_hactool=tool_hactool,
                run_cmd_fn=run_cmd_fn,
                logger=logger,
                col=col,
                tempfile_module=tempfile_module,
                verify_integrity_fn=verify_integrity_fn,
            )
        return filepath

    if args.compress and filepath.suffix.lower() != ".nsz":
        return _handle_new_compression(
            filepath,
            args=args,
            tool_nsz=tool_nsz,
            roms_dir=roms_dir,
            cmd_timeout=cmd_timeout,
            tool_metadata=tool_metadata,
            is_nstool=is_nstool,
            keys_path=keys_path,
            tool_hactool=tool_hactool,
            run_cmd_fn=run_cmd_fn,
            logger=logger,
            col=col,
            verify_integrity_fn=verify_integrity_fn,
            shutil_module=shutil_module,
        )

    if args.decompress and filepath.suffix.lower() in NSZ_EXTENSIONS:
        return _handle_decompression(
            filepath,
            args=args,
            tool_nsz=tool_nsz,
            roms_dir=roms_dir,
            cmd_timeout=cmd_timeout,
            tool_metadata=tool_metadata,
            is_nstool=is_nstool,
            keys_path=keys_path,
            run_cmd_fn=run_cmd_fn,
            logger=logger,
            col=col,
        )

    return filepath


def safe_move_impl(
    source,
    dest,
    *,
    args,
    logger,
    get_file_hash_fn,
    get_fileops_logger_fn,
    shutil_module,
):
    try:
        from emumanager.common.fileops import safe_move as safe_move_impl_ref

        base_dir = getattr(args, "roms_dir", None) or getattr(args, "base_path", None) or None
        fileops_logger = get_fileops_logger_fn(base_dir) if base_dir else logger
        return safe_move_impl_ref(
            source,
            dest,
            args=args,
            get_file_hash=get_file_hash_fn,
            logger=fileops_logger,
        )
    except Exception:
        try:
            if getattr(args, "dry_run", False):
                return True
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil_module.move(str(source), str(dest))
            return True
        except Exception:
            logger.exception("Fallback move failed %s -> %s", source, dest)
            return False
