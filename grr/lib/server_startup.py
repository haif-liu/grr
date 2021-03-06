#!/usr/bin/env python
"""Server startup routines."""
import logging
import os
import platform

from grr.lib import config_lib
from grr.lib import local
from grr.lib import log
from grr.lib import registry
from grr.lib import stats

# pylint: disable=g-import-not-at-top
if platform.system() != "Windows":
  import pwd
# pylint: enable=g-import-not-at-top


def DropPrivileges():
  """Attempt to drop privileges if required."""
  if config_lib.CONFIG["Server.username"]:
    try:
      os.setuid(pwd.getpwnam(config_lib.CONFIG["Server.username"]).pw_uid)
    except (KeyError, OSError):
      logging.exception("Unable to switch to user %s",
                        config_lib.CONFIG["Server.username"])
      raise


# Make sure we do not reinitialize multiple times.
INIT_RAN = False


def Init():
  """Run all required startup routines and initialization hooks."""
  global INIT_RAN
  if INIT_RAN:
    return

  if hasattr(local, "stats"):
    stats.STATS = local.stats.StatsCollector()
  else:
    stats.STATS = stats.StatsCollector()

  # Set up a temporary syslog handler so we have somewhere to log problems
  # with ConfigInit() which needs to happen before we can start our create our
  # proper logging setup.
  syslog_logger = logging.getLogger("TempLogger")
  if os.path.exists("/dev/log"):
    handler = logging.handlers.SysLogHandler(address="/dev/log")
  else:
    handler = logging.handlers.SysLogHandler()
  syslog_logger.addHandler(handler)

  try:
    config_lib.SetPlatformArchContext()
    config_lib.ParseConfigCommandLine()
  except config_lib.Error:
    syslog_logger.exception("Died during config initialization")
    raise

  log.ServerLoggingStartupInit()
  registry.Init()

  # Exempt config updater from this check because it is the one responsible for
  # setting the variable.
  if not config_lib.CONFIG.ContextApplied("ConfigUpdater Context"):
    if not config_lib.CONFIG.Get("Server.initialized"):
      raise RuntimeError("Config not initialized, run \"grr_config_updater"
                         " initialize\". If the server is already configured,"
                         " add \"Server.initialized: True\" to your config.")

  INIT_RAN = True
