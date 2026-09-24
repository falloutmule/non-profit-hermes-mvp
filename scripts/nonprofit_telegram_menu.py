"""Set only the dedicated Non-Profit bot menu; no messaging methods."""
import json
import urllib.request
from pathlib import Path

COMMANDS = [('daily','Organization briefing'),('need','Needs and priorities'),('donation','Donations'),('report','Organizational reports'),('task','Internal tasks'),('inventory','Supplies and inventory'),('event','Create and manage events'),('board','Staffing, openings and standby'),('new','Start a fresh conversation'),('usage','View usage'),('status','Current status'),('model','Choose a model'),('stop','Stop the current task')]
PROFILE = Path.home()/'AppData/Local/hermes/profiles/nonprofit-v1'

def apply_menu():
    from dotenv import dotenv_values
    cfg=dotenv_values(PROFILE/'private/configuration/bindings.env')
    token=cfg['TELEGRAM_BOT_TOKEN']
    def api(method, payload=None):
        try:
            req=urllib.request.Request('https://api.telegram.org/bot'+token+'/'+method,data=json.dumps(payload or {}).encode(),headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(req,timeout=20) as r:result=json.load(r)
            if not result.get('ok'):raise ValueError()
            return result['result']
        except Exception:raise RuntimeError('Telegram menu request failed; private error details suppressed') from None
    if api('getMe')['username'].lower()!='hnonprofitbot':raise RuntimeError('Unexpected bot; menu unchanged')
    commands=[{'command':n,'description':d} for n,d in COMMANDS]
    scopes=[{'type':t} for t in ('default','all_private_chats','all_group_chats','all_chat_administrators')]
    home=cfg.get('TELEGRAM_HOME_CHANNEL','').strip()
    if home.lstrip('-').isdigit():scopes.append({'type':'chat','chat_id':int(home)})
    for scope in scopes:
        for lang in ('','en'):
            args={'scope':scope,'language_code':lang}
            api('setMyCommands',dict(args,commands=commands))
            if api('getMyCommands',args)!=commands:raise RuntimeError('Telegram menu verification mismatch')
    api('setChatMenuButton',{'menu_button':{'type':'commands'}})
    return [n for n,_ in COMMANDS]

if __name__=='__main__':
    try:print('VERIFIED_MENU '+','.join(apply_menu()))
    except Exception:raise SystemExit('MENU_UPDATE_FAILED; inspect connection, no messages sent')
