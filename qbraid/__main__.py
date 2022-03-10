from .scripts import initialize_session as init_ubuntu_session
from .scripts._test import RUNNER, close_session, delete_configs
from .scripts._test import initialize_session as init_macos_session
from .scripts._test import set_config

if RUNNER.value == 'Darwin':
    delete_configs()
    close_session()
    set_config()
    init_macos_session()
else:
    set_config()
    init_ubuntu_session()

