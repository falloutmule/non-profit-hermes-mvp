"""Dedicated pinned Non-Profit runtime bootstrap; initialize its global plugin registry in profile scope."""
import os
import sys
from pathlib import Path
PROFILE=Path.home()/'AppData/Local/hermes/profiles/nonprofit-v1'
os.environ['HERMES_HOME']=str(PROFILE)
check='--check-registry' in sys.argv
if check:sys.argv.remove('--check-registry')
# This pinned runtime has one global plugin manager. Prime it before gateway/API
# startup can discover plugins under a shared-home context.
from gateway.run import main
from hermes_cli.plugins import discover_plugins,get_plugin_command_handler
discover_plugins(force=True)
handler=get_plugin_command_handler('event')
if not handler:
    raise SystemExit('Non-Profit /event command registration failed; gateway not started.')
print('NONPROFIT_EVENT_REGISTRY_READY',flush=True)
if check:
    print(handler('board list'))
else:
    import threading
    def verify_live_registry():
        from hermes_constants import get_hermes_home
        print('NONPROFIT_EVENT_REGISTRY_LIVE=' + str(bool(get_plugin_command_handler('event'))) + ' home=' + str(get_hermes_home()), flush=True)
    timer = threading.Timer(8, verify_live_registry)
    timer.daemon = True
    timer.start()
    sys.argv = [sys.argv[0]]
    main()


