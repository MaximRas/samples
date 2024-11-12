from argparse import Namespace
from typing import Any
from typing import Mapping
import logging

import yaml

from tools.types import UrlType
from tools.types import EnvNameType

log = logging.getLogger(__name__)

user_config: Mapping[str, Any] = None
app_version = None
environment: EnvNameType = None  # type: ignore[assignment]
pytest_options: Namespace = None  # type: ignore[assignment]
web_url: UrlType = None  # type: ignore[assignment]
last_object_sent_time = None
is_beta: bool = False


def load_config(path):
    global user_config
    with open(path, 'r') as f:
        cfg = yaml.safe_load(f)

    log.info('Test config loaded')
    user_config = cfg
    return cfg


def get_env_data() -> Mapping[str, Any]:
    return user_config[environment]
