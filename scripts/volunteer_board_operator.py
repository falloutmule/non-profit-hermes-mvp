from __future__ import annotations
import json
import re
import os
import sys
from datetime import datetime, date, time, timedelta, timezone
from pathlib import Path
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError
from zoneinfo import ZoneInfo

CONFIG = Path(os.environ.get('HERMES_BOARD_CONFIG', str(Path.home() / 'AppData/Local/hermes/profiles/nonprofit-v1/private/configuration/volunteer-board.json')))
ZONE = ZoneInfo('America/Denver')

class BoardError(Exception):
    pass

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise BoardError('Board redirect refused.')

def allowed_route(method, route):
    rules = {
        'GET': r'/(?:health|ready|api/admin/events(?:/[1-9][0-9]*(?:/signups|/staffing)?)?)',
        'POST': r'/api/admin/(?:events|messages/send|signups/[1-9][0-9]*/drop|series/[a-zA-Z0-9_-]+/occurrences)',
        'PATCH': r'/api/admin/(?:events/[1-9][0-9]*|series/[a-zA-Z0-9_-]+)',
    }
    return bool(re.fullmatch(rules.get(method, r'(?!)'), route))


class BoardClient:
    def __init__(self, config=None):
        self.config = config if config is not None else json.loads(CONFIG.read_text(encoding='utf-8-sig'))
        self.base = self.config['base_url'].rstrip('/')
        if self.base != 'http://127.0.0.1:8787':
            raise BoardError('This host connector requires the configured loopback Board.')
        self.token = self.config['admin_token']
        if not isinstance(self.token, str) or len(self.token) < 32:
            raise BoardError('Board credential is missing.')

    def request(self, method, route, payload=None):
        if not allowed_route(method, route):
            raise BoardError('Unsupported Board operation.')
        data = None if payload is None else json.dumps(payload).encode()
        req = Request(self.base + route, data=data, method=method, headers={'Authorization':'Bearer '+self.token,'Content-Type':'application/json'})
        try:
            with build_opener(NoRedirect()).open(req, timeout=15) as response:
                return json.load(response)
        except HTTPError as exc:
            raise BoardError('Board returned HTTP '+str(exc.code)+'. No automatic mutation retry.') from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise BoardError('Board unavailable or invalid response. Check readiness; do not blindly retry writes.') from None

    def events(self):
        return self.request('GET', '/api/admin/events')['events']


def pantry_occurrences(now=None, weeks=12):
    now = now or datetime.now(ZONE)
    if now.tzinfo is None:
        raise BoardError('Timezone-aware clock required.')
    local = now.astimezone(ZONE)
    day = local.date() + timedelta(days=(5-local.weekday()) % 7)
    if datetime.combine(day, time(15,45), ZONE) <= local:
        day += timedelta(days=7)
    result=[]
    for week in range(weeks):
        d=day+timedelta(days=7*week)
        utc=lambda t: datetime.combine(d,t,ZONE).astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
        result.append(dict(slug='PANTRY'+d.strftime('%Y%m%d'),name='Saturday Pantry',description='Every Saturday, 3:45–5:00 PM America/Denver. Six confirmed places; additional volunteers join standby. Each dated event has its own signup.',location='302 South Ave, Grand Junction, CO',startsAt=utc(time(15,45)),endsAt=utc(time(17)),capacity=6,status='draft',staffingEnabled=True,standbyEnabled=True,completionReportRequired=False,timezone='America/Denver',seriesId='saturday-pantry',occurrenceDate=d.isoformat(),recurrenceRule=json.dumps({'frequency':'weekly','weekday':5,'startTime':'15:45','endTime':'17:00','timezone':'America/Denver','horizon':12})))
    return result


def prepare_pantry(client, now=None):
    existing={e['slug']:e for e in client.events()}
    created=[]
    for event in pantry_occurrences(now):
        prior=existing.get(event['slug'])
        if prior:
            # Never overwrite operator changes or reset a published/cancelled occurrence.
            for key in ('name','location','capacity'):
                if prior[key]!=event[key]:
                    raise BoardError('Existing Pantry occurrence differs; review '+event['slug']+'.')
            for key in ('startsAt','endsAt'):
                if datetime.fromisoformat(prior[key].replace('Z','+00:00')) != datetime.fromisoformat(event[key].replace('Z','+00:00')):
                    raise BoardError('Existing Pantry time differs; review '+event['slug']+'.')
            continue
        saved=client.request('POST','/api/admin/events',event)
        existing[event['slug']]=saved
        created.append(saved)
    return created


def materialize_series(client, series_id='saturday-pantry', now=None):
    existing = client.events()
    series = [e for e in existing if e.get('seriesId') == series_id]
    if not series and series_id == 'saturday-pantry':
        # Initial adoption only: exact existing Pantry definitions are checked by Board.
        generated = pantry_occurrences(now)
    elif series:
        template = sorted(series, key=lambda e:e['startsAt'])[-1]
        rule = json.loads(template['recurrenceRule'])
        if rule.get('frequency') != 'weekly': raise BoardError('Only weekly recurrence is currently supported.')
        zone = ZoneInfo(rule['timezone']); instant = (now or datetime.now(zone)).astimezone(zone)
        start_time = time.fromisoformat(rule['startTime']); end_time = time.fromisoformat(rule['endTime'])
        weekday = int(rule['weekday']); horizon = int(rule.get('horizon',12))
        if not 0<=weekday<=6 or not 1<=horizon<=52 or end_time<=start_time: raise BoardError('Invalid weekly recurrence.')
        first = instant.date()+timedelta(days=(weekday-instant.weekday())%7)
        if datetime.combine(first,start_time,zone)<=instant:first+=timedelta(days=7)
        generated=[]
        keys=('name','description','location','capacity','staffingEnabled','standbyEnabled','completionReportRequired','completionStatement','timezone','seriesId','recurrenceRule')
        by_date={e.get('occurrenceDate'):e for e in series}
        for i in range(horizon):
            day=first+timedelta(weeks=i)
            prior=by_date.get(day.isoformat())
            if prior: continue # never overwrite edited/published/cancelled occurrences
            item={k:template[k] for k in keys if k in template}
            slug=('PANTRY' if series_id=='saturday-pantry' else series_id[:48]+'-')+day.strftime('%Y%m%d')
            item.update(slug=slug,status='draft',occurrenceDate=day.isoformat(),startsAt=datetime.combine(day,start_time,zone).astimezone(timezone.utc).isoformat().replace('+00:00','Z'),endsAt=datetime.combine(day,end_time,zone).astimezone(timezone.utc).isoformat().replace('+00:00','Z'))
            generated.append(item)
    else: raise BoardError('Create the first recurring draft before materializing its series.')
    if not generated:return {'events':[]}
    return client.request('POST','/api/admin/series/'+series_id+'/occurrences',{'events':generated})


def local_time(value):
    return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(ZONE)


def clock(value):
    return value.strftime('%I:%M %p').lstrip('0')


def event_details(event):
    start, end = local_time(event['startsAt']), local_time(event['endsAt'])
    status = {'draft': 'Not published yet', 'published': 'Open for signups',
              'cancelled': 'Cancelled', 'completed': 'Completed'}.get(event['status'], event['status'])
    return '\n'.join([
        event['name'],
        start.strftime('%A, %B ') + str(start.day) + start.strftime(', %Y'),
        f"{clock(start)}–{clock(end)} · Denver time",
        event.get('location') or 'Location to be announced',
        ((f"{event['capacity']} volunteer places" + (" · Standby when full" if event.get("standbyEnabled", True) else "")) if event.get("staffingEnabled", True) else "Staffing off"),
        ("Completion: text DONE after finishing" if event.get("completionReportRequired") else "No SMS completion report required"),
        '', status,
        (f"Signup keyword: {event['slug']}" if event.get("staffingEnabled", True) else ""),
        'No signups are accepted until published.' if event['status'] == 'draft' else '',
    ]).rstrip()


def summary(events, page=1):
    if not events:
        return 'No volunteer events yet.'
    events = sorted(events, key=lambda e: (e['startsAt'], str(e['id'])))
    pages = (len(events) + 2) // 3
    if page < 1 or page > pages:
        return f"Choose a page from 1 to {pages}: /board <page>"
    visible = events[(page-1)*3:page*3]
    def group_key(e):
        start, end = local_time(e['startsAt']), local_time(e['endsAt'])
        return (e['name'], e.get('location'), e['capacity'], e['status'],
                start.weekday(), clock(start), clock(end))
    first = events[0]
    if all(group_key(e) == group_key(first) for e in events):
        start, end = local_time(first['startsAt']), local_time(first['endsAt'])
        lines = [first['name'],
                 f"{start:%A}s · {clock(start)}–{clock(end)} (Denver)",
                 first.get('location') or 'Location to be announced',
                 f"{first['capacity']} volunteer places per date · Standby when full", '',
                 'Not published yet' if first['status'] == 'draft' else first['status'].capitalize(),
                 f"Dates ({len(events)} prepared)"]
        for event in visible:
            dt = local_time(event['startsAt'])
            lines.append(f"• {dt:%b} {dt.day}, {dt.year}")
    else:
        lines = ['Volunteer events', '']
        for event in visible:
            dt = local_time(event['startsAt'])
            label = 'Not published' if event['status'] == 'draft' else event['status'].capitalize()
            lines.append(f"• {event['name']} — {dt:%b} {dt.day}, {clock(dt)} (Denver) · {label}")
    lines.append('')
    if isinstance(visible[0]['id'], int):
        lines.append(f"First date details: /board show {visible[0]['id']}")
    if page < pages:
        lines.append(f"More dates: /board {page+1}")
    return '\n'.join(lines)


def operate(action, payload=None, *, client=None, authorized=False):
    """Structured operator boundary; never logs bodies, credentials or private rosters."""
    client = client or BoardClient()
    payload = payload or {}
    if action == 'status':
        return {key: client.request('GET', '/' + key) for key in ('health', 'ready')}
    if action == 'list':
        return {'events': client.events()}
    def positive_id(key):
        value = payload.get(key)
        if type(value) is not int or value < 1:
            raise BoardError('A positive integer ' + key + ' is required.')
        return value
    if action in ('show', 'signups'):
        event_id = positive_id('eventId')
        event = client.request('GET', '/api/admin/events/' + str(event_id))
        if action == 'show': return event
        rows = client.request('GET', '/api/admin/events/' + str(event_id) + '/signups')['signups']
        return {'eventId': event_id, 'capacity': event['capacity'],
                'counts': {state: sum(row['status'] == state for row in rows) for state in ('confirmed','standby','cancelled')},
                'signups': [{key: row.get(key) for key in ('id','volunteerId','status','standbyPosition','smsStatus')} for row in rows]}
    if action not in ('create', 'update', 'send', 'drop', 'series_prepare', 'series_update'):
        raise BoardError('Unsupported operation.')
    if authorized is not True:
        raise BoardError('Explicit operator authorization required; no change made.')
    if action in ('series_prepare','series_update'):
        series_id=payload.get('seriesId','')
        if not re.fullmatch(r'[A-Za-z0-9_-]+',series_id):raise BoardError('Invalid series ID.')
        if action=='series_prepare':return materialize_series(client,series_id)
        changes=payload.get('occurrenceChanges')
        if not isinstance(changes,list) or not changes:raise BoardError('Explicit per-occurrence changes required; specify one or future dates.')
        for change in changes:
            if set(change.get('patch',{})) & {'status','seriesId','slug','occurrenceDate'}:raise BoardError('Series schedule edits cannot publish or change identity.')
        return client.request('PATCH','/api/admin/series/'+series_id,{'occurrenceChanges':changes})
    if action in ('send', 'drop') and client.config.get('real_use_review_complete') is not True:
        raise BoardError('Real-use review remains held; no SMS-capable action made.')
    if action in ('create', 'update'):
        fields = payload.get('event')
        allowed = {'slug','name','description','location','startsAt','endsAt','capacity','status','staffingEnabled','standbyEnabled','completionReportRequired','completionStatement','timezone','seriesId','recurrenceRule','occurrenceDate'}
        if not isinstance(fields, dict) or not fields or set(fields) - allowed:
            raise BoardError('Invalid event fields.')
        if action == 'create' and fields.get('status') != 'draft':
            raise BoardError('Create a draft first.')
        if fields.get('status') == 'published' and client.config.get('real_use_review_complete') is not True:
            raise BoardError('Publication review remains held.')
        if action=='update':
            current=client.request('GET','/api/admin/events/'+str(positive_id('eventId')))
            if current.get('seriesId') and any(k in fields for k in ('startsAt','endsAt','capacity','recurrenceRule')) and payload.get('scope')!='one':
                raise BoardError('Recurring edit requires scope=one or an explicit series_update for future occurrences.')
            if fields.get('status')=='completed' and current['status']=='draft':
                raise BoardError('A draft cannot be completed; cancel it instead.')
        route = '/api/admin/events'
        if action == 'update': route += '/' + str(positive_id('eventId'))
        return client.request('POST' if action == 'create' else 'PATCH', route, fields)
    if action == 'drop':
        return client.request('POST', '/api/admin/signups/' + str(positive_id('signupId')) + '/drop', {})
    message = {'volunteerId': positive_id('volunteerId'), 'body': payload.get('body')}
    if not isinstance(message['body'], str) or not 1 <= len(message['body'].strip()) <= 1600:
        raise BoardError('Invalid message body.')
    if 'eventId' in payload: message['eventId'] = positive_id('eventId')
    result = client.request('POST', '/api/admin/messages/send', message)
    return {'accepted': True, 'status': result.get('status', 'unknown')}


def dispatch(args, client=None):
    try:
        words=args.strip().split()
        if not words or words==['help']:
            return 'Volunteer events\n\n/board — Upcoming dates\n/board show <id> — Event details\n/board pantry prepare — Prepare upcoming Saturdays\n/board publish <id> — Publish a reviewed date'
        if words==['pantry','preview']:
            return summary([dict(e,id='draft') for e in pantry_occurrences()])
        client=client or BoardClient()
        if words==['status']:
            state=operate('status',client=client)
            return 'Volunteer Board: ' + ('Ready' if all(v.get('ok') is True for v in state.values()) else 'Needs attention')
        if len(words)==2 and words[0]=='signups' and words[1].isdigit():
            state=operate('signups',{'eventId':int(words[1])},client=client)
            return f"Places: {state['capacity']} · Confirmed: {state['counts']['confirmed']} · Standby: {state['counts']['standby']}"
        if words==['list']:return summary(client.events())
        if len(words)==2 and words[0]=='list' and words[1].isdigit():
            return summary(client.events(), int(words[1]))
        if words==['pantry','prepare']:
            result=materialize_series(client)
            created=result.get('events',[])
            return f'Prepared {len(created)} new Saturday Pantry drafts; upcoming 12 Saturdays reconciled without overwriting existing events. No SMS sent. Use /board.'
        if len(words)==2 and words[0] in ('show','publish') and words[1].isdigit() and int(words[1])>0:
            route='/api/admin/events/'+str(int(words[1]))
            if words[0]=='show':return event_details(client.request('GET',route))
            if client.config.get('real_use_review_complete') is not True:
                return 'Publication held: current public wording and approved campaign real-use review must be confirmed first. No change made.'
            event=client.request('GET',route)
            if event['status']!='draft':return 'Only a draft can be published through this command. No change made.'
            return event_details(client.request('PATCH',route,{'status':'published'}))
        return 'Unknown Board command. Use /board help. No SMS or drop operation is exposed here.'
    except Exception:
        # No credential, HTTP header, raw API body, private roster or traceback in Telegram.
        return 'Volunteer Board operation failed. Inspect local readiness/configuration and reconcile events before retrying a write. No secrets displayed.'

if __name__=='__main__':
    if sys.argv[1:] == ['--request']:
        try:
            request=json.load(sys.stdin)
            result=operate(request['action'],request.get('payload'),authorized=request.get('authorized') is True)
            print(json.dumps(result,ensure_ascii=True))
        except Exception:
            print(json.dumps({'error':'Board operation failed or held; reconcile before retrying writes.'}))
            sys.exit(1)
    else:
        result = dispatch(' '.join(sys.argv[1:]))
        print(result)
        sys.exit(1 if result.startswith('Volunteer Board operation failed.') else 0)
