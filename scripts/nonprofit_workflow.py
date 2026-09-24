"""Shared, bounded Telegram and natural-language nonprofit operations."""
from __future__ import annotations
import importlib.util
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from volunteer_board_operator import BoardClient, BoardError, operate, event_details, summary

HELP = {
    'need': 'Needs\nTell me what is needed, how much, and its priority.\nExample: Create a need for 10 pairs of winter gloves.',
    'donation': 'Donations\nTell me what was donated and its purpose.\nExample: Record a $40 food donation.\nI will ask for any required details.',
    'report': 'Reports\nTell me what happened and the report date.\nI use recorded facts and keep private details out of shared reports.',
    'task': 'Tasks\nTell me the task, owner, and due date.\nExample: Create a task to count the pantry supplies on Friday.',
    'inventory': 'Inventory\nTell me the item, quantity, and unit.\nExample: Record 10 pairs of socks in inventory.',
}

def wire_legacy(router):
    from dotenv import dotenv_values
    profile = Path.home()/'AppData/Local/hermes/profiles/nonprofit-v1'
    bindings = dotenv_values(profile/'private/configuration/bindings.env')
    os.environ['NON_PROFIT_HERMES_CREDENTIALS_FILE'] = str(Path.home()/'AppData/Local/hermes/google_token.json')
    for key in ('NON_PROFIT_HERMES_SPREADSHEET_ID','NON_PROFIT_HERMES_CALENDAR_ID'):
        if bindings.get(key): os.environ.setdefault(key,bindings[key])
    from non_profit_hermes import operations
    from google_oauth_refresh import refresh_and_persist_credential
    operations.TOKEN = Path.home()/'AppData/Local/hermes/google_token.json'
    operations.refresh_and_persist_credential = refresh_and_persist_credential
    return router


def legacy_router():
    try:
        from non_profit_hermes import router
        return wire_legacy(router)
    except ModuleNotFoundError as exc:
        if exc.name != 'non_profit_hermes': raise
        # Main-runtime /restart can run outside the dedicated venv. Load only
        # this existing package, without putting an entire venv on sys.path.
        package = Path.home() / 'AppData/Local/hermes/staging/non-profit-hermes-v1/20260804T170601Z/telegram-canary-remediation-20260805T100000Z/venv-telegram-fresh/Lib/site-packages/non_profit_hermes'
        spec = importlib.util.spec_from_file_location('non_profit_hermes', package / '__init__.py', submodule_search_locations=[str(package)])
        module = importlib.util.module_from_spec(spec)
        sys.modules['non_profit_hermes'] = module
        spec.loader.exec_module(module)
        from non_profit_hermes import router
        return wire_legacy(router)

def inspection_link():
    try:
        from member_operations_projection import inspection_status
        status = inspection_status()
        return '\nMember operations: ' + str(status.get('url') or 'Not initialized') + '\nGoogle sync: ' + str(status.get('status', 'unknown'))
    except Exception:
        return '\nGoogle inspection status unavailable.'

def staffing_text(event_id, client):
    state = client.request('GET', f'/api/admin/events/{event_id}/staffing')
    event = client.request('GET', f'/api/admin/events/{event_id}')
    counts = state.get('counts', {})
    confirmed = state.get('confirmedCount', counts.get('confirmed', 0))
    standby = state.get('standbyCount', counts.get('standby', 0))
    reserved = state.get('pendingOfferCount', state.get('reservedCount', 0))
    available = state.get('spotsAvailable', max(0, event['capacity']-confirmed-reserved))
    if not event.get('staffingEnabled', True):
        return f"{event['name']}\nStaffing is off · {event['status']}"
    lines = [event['name'], f"Confirmed: {confirmed}/{event['capacity']} · Open: {available}", f"Standby: {standby} · Pending offers: {reserved}", 'Status: '+event['status']]
    for row in state.get('signups', []):
        name = row.get('displayName') or 'Volunteer #'+str(row['volunteerId'])
        position = f" #{row['standbyPosition']}" if row.get('standbyPosition') is not None and row['status']=='standby' else ''
        lines.append(f"• {name}: {row['status']}{position}")
    completion = state.get('completion')
    if completion: lines.append('Completed: '+str(completion.get('statement', completion.get('completionStatement',''))))
    return '\n'.join(lines)

def board(args='', client=None):
    client = client or BoardClient()
    words = args.strip().split()
    if words == ['status']:
        state = operate('status', client=client)
        return ('Volunteer Board: Ready' if all(x.get('ok') for x in state.values()) else 'Volunteer Board needs attention') + inspection_link()
    if len(words)==2 and words[0] in ('show','signups') and words[1].isdigit():
        return staffing_text(int(words[1]),client)
    if words and words[0] in ('create','update','publish','pantry','cancel','complete'):
        return 'Use /event for event changes. /board shows staffing and signup state.'
    page = int(words[0]) if len(words)==1 and words[0].isdigit() else int(words[1]) if len(words)==2 and words[0]=='list' and words[1].isdigit() else 1
    if words and words not in (['help'],['list']) and not (len(words)==1 and words[0].isdigit()) and not (len(words)==2 and words[0]=='list' and words[1].isdigit()):
        return 'Staffing\n/board — Upcoming events\n/board show 1 — People, openings and standby\n/board status — Service and Google sync'
    rows = client.events()
    if not rows:return 'No events yet. Use /event to create a draft.'
    rows=sorted(rows,key=lambda x:x['startsAt'])
    pages=(len(rows)+2)//3
    if page<1 or page>pages:return f'Choose page 1–{pages}.'
    shown=rows[(page-1)*3:page*3]
    lines=['Volunteer staffing','']
    from volunteer_board_operator import local_time,clock
    for event in shown:
        dt=local_time(event['startsAt'])
        lines.append(f"{event['name']} · {dt:%b} {dt.day} · {clock(dt)}")
        lines.extend(staffing_text(event['id'],client).splitlines()[1:4])
        lines.append(f"Details: /board show {event['id']}\n")
    if page<pages:lines.append(f'More: /board {page+1}')
    return '\n'.join(lines)

def event(args='', client=None):
    client=client or BoardClient()
    words=args.strip().split(maxsplit=2)
    if not words or words==['list']:
        return summary(client.events()).replace('/board','/event') + '\n\nTo create or change an event, tell me what, when and where in a regular message.'
    if words[0]=='board': return board(args.strip()[5:].strip(),client)
    if words[0].isdigit():return summary(client.events(),int(words[0])).replace('/board','/event')
    if len(words)==2 and words[0]=='show' and words[1].isdigit():
        return event_details(operate('show',{'eventId':int(words[1])},client=client))
    if len(words)==2 and words[0] in ('publish','cancel','complete') and words[1].isdigit():
        status={'publish':'published','cancel':'cancelled','complete':'completed'}[words[0]]
        return event_details(operate('update',{'eventId':int(words[1]),'event':{'status':status}},client=client,authorized=True))
    if words[0]=='create':
        fields=json.loads(args.strip()[len('create'):].strip())
        fields.setdefault('status','draft');fields.setdefault('staffingEnabled',False);fields.setdefault('standbyEnabled',False);fields.setdefault('completionReportRequired',False)
        return event_details(operate('create',{'event':fields},client=client,authorized=True))
    if len(words)==3 and words[0]=='update' and words[1].isdigit():
        return event_details(operate('update',{'eventId':int(words[1]),'scope':'one','event':json.loads(words[2])},client=client,authorized=True))
    return 'Events\n/event — Upcoming dates\n/event show 1 — Event details\nTell me the event name, date, time and location in a regular message. I will ask about staffing and DONE completion when needed. New events stay drafts.'

def daily(client=None):
    lines=['Today at Hermes']
    try:
        from member_operations_projection import Google, member_rows, now, load, DEFAULT_CONFIG
        sources=Google().sources()
        config=load(DEFAULT_CONFIG) if DEFAULT_CONFIG.exists() else {}
        views=member_rows({},sources,now(),config.get('approved_record_ids'))
        closed={'complete','completed','resolved','cancelled','closed'}
        for label,source in [('Needs','Requests'),('Tasks','Tasks')]:
            rows=sources.get(source,[])
            active=sum(str(r.get('Status','')).lower() not in closed for r in rows)
            lines.append(f'{label}: {active} not marked closed · {len(rows)} recorded')
        lines.append(f"Donations: {len(sources.get('Donations',[]))} recorded · Reports: {len(sources.get('Reports',[]))} recorded")
        warnings=[]
        for r in views['Inventory'][1:]:
            try:
                if float(r[2]) < float(r[4]):warnings.append(f'{r[1]}: {r[2]} {r[3]} (minimum {r[4]})')
            except (ValueError,TypeError):pass
        lines.append('Inventory: '+('; '.join(warnings[:3]) if warnings else 'No below-minimum quantities in the available numeric records.'))
        if len(warnings)>3:lines.append(f'{len(warnings)-3} more inventory warnings in Member Operations.')
        lines.append('Details use the shared inspection views; private record text is withheld.')
    except Exception:
        lines.append('Google records unavailable; no figures inferred.')
    try: lines.extend(['',board('',client)])
    except Exception: lines.append('Volunteer staffing unavailable.')
    return '\n'.join(lines)+inspection_link()

def dispatch(command,args='',client=None):
    try:
        if command=='event':return event(args,client)
        if command=='board':return board(args,client)
        if command=='daily':return daily(client)
        if command in HELP:
            if not args.strip() or args.strip()=='help':return HELP[command]
            return legacy_router().run_plugin_command(command,args)
        return 'Unknown nonprofit operation.'
    except BoardError as exc:
        return str(exc) # BoardError messages are explicitly redacted at their source.
    except Exception:
        return 'Operation could not be completed. No automatic write retry; check the recorded state before trying again.'

if __name__=='__main__':
    print(dispatch(sys.argv[1] if len(sys.argv)>1 else 'daily',' '.join(sys.argv[2:])))
