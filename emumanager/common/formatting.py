def human_readable_size(num: int) -> str:
    """Convert bytes to a human readable string using binary prefixes.

    Examples:
    - 123 -> '123 B'
    - 2048 -> '2.0 KB'
    - 5_242_880 -> '5.0 MB'
    """
    try:
        n = int(num)
    except Exception:
        return str(num)

    if n < 1024:
        return f"{n} B"

    units = ["KB", "MB", "GB", "TB", "PB"]
    value = n / 1024.0
    for u in units:
        if value < 1024.0:
            # show one decimal for values < 10, else no decimals
            if value < 10:
                return f"{value:.1f} {u}"
            return f"{value:.0f} {u}"
        value /= 1024.0

    return f"{value:.1f} PB"
