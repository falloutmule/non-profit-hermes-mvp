from __future__ import annotations
import json
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
        if not route.startswith('/api/admin/events') or method not in ('GET', 'POST', 'PATCH'):
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
        result.append(dict(slug='PANTRY'+d.strftime('%Y%m%d'),name='Saturday Pantry',description='Every Saturday, 3:45â€“5:00 PM America/Denver. Six confirmed places; additional volunteers join standby. Each dated event has its own signup.',location='302 South Ave, Grand Junction, CO',startsAt=utc(time(15,45)),endsAt=utc(time(17)),capacity=6,status='draft'))
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
        f"{event['capacity']} volunteer places · Standby when full",
        '', status,
        f"Signup keyword: {event['slug']}",
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


def dispatch(args, client=None):
    try:
        words=args.strip().split()
        if not words or words==['help']:
            return 'Volunteer events\n\n/board — Upcoming dates\n/board show <id> — Event details\n/board pantry prepare — Prepare upcoming Saturdays\n/board publish <id> — Publish a reviewed date'
        if words==['pantry','preview']:
            return summary([dict(e,id='draft') for e in pantry_occurrences()])
        client=client or BoardClient()
        if words==['list']:return summary(client.events())
        if len(words)==2 and words[0]=='list' and words[1].isdigit():
            return summary(client.events(), int(words[1]))
        if words==['pantry','prepare']:
            created=prepare_pantry(client)
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
    result = dispatch(' '.join(sys.argv[1:]))
    print(result)
    sys.exit(1 if result.startswith('Volunteer Board operation failed.') else 0)

