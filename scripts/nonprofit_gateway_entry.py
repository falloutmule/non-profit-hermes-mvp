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
COMMANDS=('daily','need','donation','report','task','inventory','event','board')
handler=get_plugin_command_handler('board')
if not all(get_plugin_command_handler(name) for name in COMMANDS):
    raise SystemExit('Non-Profit /board command registration failed; gateway not started.')
print('NONPROFIT_COMMAND_REGISTRY_READY='+','.join(COMMANDS),flush=True)
if check:
    print(handler(''))
else:
    import threading
    def verify_live_registry():
        from hermes_constants import get_hermes_home
        print('NONPROFIT_COMMAND_REGISTRY_LIVE=' + str(all(get_plugin_command_handler(name) for name in COMMANDS)) + ' home=' + str(get_hermes_home()), flush=True)
    def restore_menu():
        try:
            from nonprofit_telegram_menu import apply_menu
            print('NONPROFIT_MENU_VERIFIED=' + ','.join(apply_menu()), flush=True)
        except Exception:
            print('NONPROFIT_MENU_FAILED: inspect connection; no messages sent', flush=True)
    menu_timer = threading.Timer(15, restore_menu)
    menu_timer.daemon = True
    menu_timer.start()
    timer = threading.Timer(8, verify_live_registry)
    timer.daemon = True
    timer.start()
    sys.argv = [sys.argv[0]]
    main()


