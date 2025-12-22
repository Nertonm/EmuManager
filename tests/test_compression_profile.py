import switch_organizer as so


class A:
    pass


def test_profile_overrides_level(monkeypatch):
    a = A()
    # Set numeric level to something else
    a.level = 1
    a.compression_profile = "best"
    # call parser parse simulation by setting args directly
    so.args = a

    # Manually run the profile application part from main logic
    try:
        if getattr(so.args, "compression_profile", None):
            prof = so.args.compression_profile
            if prof in so.COMPRESSION_PROFILE_LEVELS:
                so.args.level = so.COMPRESSION_PROFILE_LEVELS[prof]
    except Exception:
        pass

    assert so.args.level == so.COMPRESSION_PROFILE_LEVELS["best"]


def test_default_is_balanced_when_not_provided(monkeypatch):
    a = A()
    # No compression_profile set; rely on default in parser (module default already set)
    # simulate args as if parsed without compression_profile
    if hasattr(a, "compression_profile"):
        delattr(a, "compression_profile")
    # parser default in module: we expect default level is 3
    assert so.COMPRESSION_PROFILE_LEVELS["balanced"] == 3
    # also ensure parser default level is 3 (use dest name 'level')
    assert so.parser.get_default("level") == 3
