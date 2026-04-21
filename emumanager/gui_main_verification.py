from .gui_main_verification_dat import MainWindowVerificationDatMixin
from .gui_main_verification_dats import MainWindowVerificationDatsMixin
from .gui_main_verification_identify import MainWindowVerificationIdentifyMixin
from .gui_main_verification_rehash import MainWindowVerificationRehashMixin
from .gui_main_verification_results import MainWindowVerificationResultsMixin


class MainWindowVerificationMixin(
    MainWindowVerificationDatMixin,
    MainWindowVerificationRehashMixin,
    MainWindowVerificationResultsMixin,
    MainWindowVerificationDatsMixin,
    MainWindowVerificationIdentifyMixin,
):
    """Stable façade for verification-related GUI behavior split across focused mixins."""

    pass
