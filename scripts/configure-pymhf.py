"""Configure NMS.py paths without the first-run folder picker."""

from __future__ import annotations

import os
from pathlib import Path

import tomlkit

config_path = Path(os.environ["NMSDL_PYMHF_CONFIG"])
document = (
    tomlkit.parse(config_path.read_text(encoding="utf-8"))
    if config_path.exists()
    else tomlkit.document()
)

if "pymhf" not in document:
    document["pymhf"] = tomlkit.table()
pymhf_config = document["pymhf"]

if "local_config" not in pymhf_config:
    pymhf_config["local_config"] = tomlkit.table()
local_config = pymhf_config["local_config"]

if "logging" not in local_config:
    local_config["logging"] = tomlkit.table()
logging_config = local_config["logging"]

local_config["mod_dir"] = os.environ["NMSDL_MOD_DIRECTORY"]
local_config["start_paused"] = True
logging_config["log_dir"] = os.environ["NMSDL_LOG_DIRECTORY"]
logging_config["shown"] = False

config_path.write_text(tomlkit.dumps(document), encoding="utf-8")
