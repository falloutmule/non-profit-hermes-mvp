"""One-way member inspection projection. No volunteer writes and no SMS operations."""
from __future__ import annotations
import argparse, hashlib, json, os, sys, time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, build_opener, HTTPRedirectHandler
from zoneinfo import ZoneInfo

DEFAULT_CONFIG = Path.home() / 'AppData/Local/hermes/profiles/nonprofit-v1/private/configuration/member-operations.json'
TABS = ['Overview','Events','Staffing','Needs','Tasks','Inventory','Donations Summary','Reports','Activity','Sync Status']
SAFE_PRIVACY = {'board-visible','public-safe','member-visible'}

def now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def load(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def save(path, value):
    path=Path(path); tmp=path.with_suffix('.tmp'); tmp.write_text(json.dumps(value,indent=2),encoding='utf-8'); os.replace(tmp,path)
def inspection_status(config_path=DEFAULT_CONFIG):
    try:
        c=load(config_path)
        return {'url':'https://docs.google.com/spreadsheets/d/'+c['workbook_id'] if c.get('workbook_id') else None,'last_success':c.get('last_success'),'status':c.get('status','not initialized')}
    except (OSError,ValueError): return {'url':None,'last_success':None,'status':'not initialized'}

@contextmanager
def exclusive(path):
    # Kernel releases lock on process death. Never remove the lock inode while held.
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a+b') as f:
        f.seek(0); f.write(b'0'); f.flush(); f.seek(0)
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try: yield
        finally:
            f.seek(0)
            if os.name=='nt': msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
            else: fcntl.flock(f,fcntl.LOCK_UN)

def cell(v):
    # RAW sheets writes prevent formula interpretation; limit unexpected free text.
    return '' if v is None else str(v)[:1000]
def approved(r): return str(r.get('PrivacyLevel','')).lower() in SAFE_PRIVACY
def yes(v): return str(v).lower() in {'true','yes','1','approved'}
def records(values):
    if not values: return []
    return [dict(zip(values[0],r)) for r in values[1:] if any(r)]
def local(v):
    return datetime.fromisoformat(v.replace('Z','+00:00')).astimezone(ZoneInfo('America/Denver')).strftime('%Y-%m-%d %I:%M %p %Z') if v else ''

def member_rows(snapshot, sources, timestamp, approved_record_ids=None):
    """Allowlist-only projection: unknown columns never pass through."""
    approved_record_ids=approved_record_ids or {}
    events=snapshot.get('events',[]); names={e['id']:e['name'] for e in events}
    out={}
    out['Events']=[['Board ID','Event','Start (Denver)','End (Denver)','Location','Status','Staffing','Capacity','Confirmed','Reserved offers','Openings','Standby','Completion required','Completed at','Completed by','Completion statement']]
    for e in events:
        c=e.get('completion') or {}
        out['Events'].append([e['id'],e['name'],local(e.get('startsAt')),local(e.get('endsAt')),e.get('location',''),e['status'],e.get('staffingEnabled',True),e['capacity'],e.get('confirmedCount',0),e.get('reservedCount',0),e.get('spotsAvailable',0),e.get('standbyCount',0),e.get('completionReportRequired',False),c.get('completedAt',''),c.get('displayName') or ('Volunteer #'+str(c['volunteerId']) if c.get('volunteerId') else ''),c.get('statement','')])
    out['Staffing']=[['Signup ID','Board event ID','Event','Volunteer','Status','Standby position','Updated']]
    for s in snapshot.get('staffing',[]):
        out['Staffing'].append([s['id'],s['eventId'],names.get(s['eventId'],''),s.get('displayName') or 'Volunteer #'+str(s['volunteerId']),s['status'],s.get('standbyPosition',''),s.get('updatedAt','')])
    specifications={
        'Needs':('Requests',['RequestID','NeedCategory','NeedDescription','Quantity','Status','Urgency','NeededBy'],approved),
        'Tasks':('Tasks',['TaskID','TaskTitle','Status','AssignedTo','DueDate','Priority'],lambda r:approved(r) or (not r.get('PrivacyLevel') and r.get('TaskID') in approved_record_ids.get('Tasks',[]))),
        'Inventory':('Inventory',['ItemID','ItemName','QuantityOnHand','Unit','MinimumNeeded','Status'],lambda r:not r.get('PrivacyLevel') or approved(r)),
        'Donations Summary':('Donations',['DonationID','DateOffered','DonationType','ItemDescription','Quantity','Status'],approved),
        'Reports':('Reports',['ReportID','Date','ReportType','PublicSummaryDraft','Status'],lambda r:approved(r) and bool(r.get('PublicSummaryDraft','').strip())),
    }
    for target,(source,fields,gate) in specifications.items():
        out[target]=[fields]+[[r.get(k,'') for k in fields] for r in sources.get(source,[]) if gate(r)]
    out['Activity']=[['Source ID','Timestamp','Source','Action','Target','Result']]
    for a in snapshot.get('activity',[]):
        out['Activity'].append(['board:'+str(a['id']),a['createdAt'],a['source'],a['action'],a['target'],a['result']])
    # Audit free text/actors/targets may contain private contact data. Expose only
    # references whose underlying record is already included in a sanitized view.
    # Legacy AuditLog targets are source-tab/ID. Bare IDs are supported only
    # when unique across ALL sources, including withheld private records.
    from collections import Counter
    id_counts=Counter(); qualified_counts=Counter(); visible=set()
    for source,fields,_gate in specifications.values():
        for record in sources.get(source,[]):
            identity=str(record.get(fields[0],''))
            if identity:
                id_counts[identity]+=1;qualified_counts[source+'/'+identity]+=1
    for tab,(source,_fields,_gate) in specifications.items():
        for row in out[tab][1:]:
            identity=str(row[0]); qualified=source+'/'+identity
            if identity and qualified_counts[qualified]==1:
                visible.add(qualified)
                if id_counts[identity]==1:visible.add(identity)
    for a in sources.get('AuditLog',[]):
        if a.get('TargetItem') in visible and a.get('Action') in {'create','update','complete','resolve','delete','cancel'}:
            out['Activity'].append(['google:'+a.get('AuditID',''),a.get('Timestamp',''),'Google operations',a['Action'],a['TargetItem'],'Recorded'])
    out['Overview']=[['Hermes Non-Profit — Member Operations','Generated inspection view; edits never change operational sources.'],['Updated UTC',timestamp],['Board source','Volunteer Board authenticated API'],['Google source','Existing private operations workbook'],['Privacy','Only explicitly shareable source records are mirrored. Unclassified Tasks are withheld.'],['Amounts','Donation monetary value is unavailable in the current source schema.']]+[[tab,len(out[tab])-1] for tab in ['Events','Staffing','Needs','Tasks','Inventory','Donations Summary','Reports']]
    for source in ['Requests','Tasks','Inventory','Donations','Reports']:
        source_rows=sources.get(source,[])
        out['Overview'].append([source+' source records',len(source_rows)])
        for status in ['new','open','ready','in-progress','needs-info','complete','completed','cancelled']:
            count=sum(str(r.get('Status','')).lower()==status for r in source_rows)
            if count:out['Overview'].append([source+' / '+status,count])
    out['Sync Status']=[['Status','Generated at UTC','Board snapshot at UTC'],['Last successful snapshot; check timestamp age (not a live guarantee)',timestamp,snapshot.get('generatedAt','')]]
    return {tab:[[cell(v) for v in row] for row in rows] for tab,rows in out.items()}

class Board:
    def __init__(self,path):
        c=load(path)
        if c['base_url'].rstrip('/')!='http://127.0.0.1:8787': raise ValueError('Loopback Board required')
        self.base=c['base_url'].rstrip('/'); self.token=c['admin_token']
    def call(self,route,payload=None):
        if route not in {'snapshot','pending','ack'}: raise ValueError('Unsupported projection operation')
        class NoRedirect(HTTPRedirectHandler):
            def redirect_request(self,*args,**kwargs): raise ValueError('Redirect refused')
        req=Request(self.base+'/api/admin/projection/'+route,data=json.dumps(payload).encode() if payload is not None else None,headers={'Authorization':'Bearer '+self.token,'Content-Type':'application/json'})
        with build_opener(NoRedirect()).open(req,timeout=30) as r:return json.load(r)

def calendar_id(event_id):return 'hermesboard'+hashlib.sha256(('hermes-volunteer-board:'+str(event_id)).encode()).hexdigest()[:40]

class Google:
    def __init__(self):
        import non_profit_hermes_ops as ops
        from googleapiclient.discovery import build
        creds=ops.get_creds(); self.sheets=ops.sheets(creds); self.calendar=ops.calendar(creds); self.drive=build('drive','v3',credentials=creds)
        self.source=ops.SPREADSHEET_ID; self.calendar_target=ops.CALENDAR_ID
    def sources(self):
        tabs=['Requests','Tasks','Inventory','Donations','Reports','AuditLog','CalendarLog']
        data=self.sheets.spreadsheets().values().batchGet(spreadsheetId=self.source,ranges=["'"+t+"'!A:AZ" for t in tabs]).execute()
        return {t:records(v.get('values',[])) for t,v in zip(tabs,data['valueRanges'])}
    def initialize(self,config):
        # File appProperties make interrupted initialization rediscoverable.
        key='hermes-member-operations-v1'
        found=self.drive.files().list(q="trashed = false and appProperties has { key='hermesProjection' and value='"+key+"' }",fields='files(id)',pageSize=100).execute().get('files',[])
        if len(found)>1:raise ValueError('Multiple member workbooks require review')
        if found: workbook=found[0]['id']
        else:
            f=self.drive.files().create(body={'name':'Hermes Non-Profit — Member Operations','mimeType':'application/vnd.google-apps.spreadsheet','appProperties':{'hermesProjection':key}},fields='id').execute(); workbook=f['id']
        config['workbook_id']=workbook
        return workbook
    def protect(self,workbook):
        permissions=self.drive.permissions().list(fileId=workbook,fields='permissions(type,role)',pageSize=100).execute().get('permissions',[])
        if any(p['role']!='owner' for p in permissions):raise ValueError('Initialization requires owner-only workbook; sharing not changed')
        meta=self.sheets.spreadsheets().get(spreadsheetId=workbook,fields='sheets(properties,protectedRanges)').execute()
        existing={s['properties']['title']:s for s in meta['sheets']}; requests=[]
        for index,title in enumerate(TABS):
            if title not in existing:
                sid=100+index
                requests.append({'addSheet':{'properties':{'sheetId':sid,'title':title,'gridProperties':{'rowCount':1000,'columnCount':26,'frozenRowCount':1}}}})
                requests.append({'addProtectedRange':{'protectedRange':{'range':{'sheetId':sid},'description':'Generated one-way projection','warningOnly':False,'editors':{'users':[],'domainUsersCanEdit':False}}}})
            elif not existing[title].get('protectedRanges'):
                requests.append({'addProtectedRange':{'protectedRange':{'range':{'sheetId':existing[title]['properties']['sheetId']},'description':'Generated one-way projection','warningOnly':False,'editors':{'users':[],'domainUsersCanEdit':False}}}})
        if requests:self.sheets.spreadsheets().batchUpdate(spreadsheetId=workbook,body={'requests':requests}).execute()
    def write_views(self,workbook,rows):
        # One Sheets batchUpdate atomically replaces all generated cell ranges,
        # including stale trailing rows. Explicit string values cannot execute formulas.
        meta=self.sheets.spreadsheets().get(spreadsheetId=workbook,fields='sheets.properties').execute()
        tabs={s['properties']['title']:s['properties'] for s in meta['sheets']}; requests=[]
        for title,values in rows.items():
            p=tabs[title]; needed=max(1000,len(values))
            if p.get('gridProperties',{}).get('rowCount',0)<needed:
                requests.append({'updateSheetProperties':{'properties':{'sheetId':p['sheetId'],'gridProperties':{'rowCount':needed}},'fields':'gridProperties.rowCount'}})
            requests.append({'updateCells':{'range':{'sheetId':p['sheetId']},'rows':[{'values':[{'userEnteredValue':{'stringValue':cell(v)}} for v in row]} for row in values],'fields':'userEnteredValue'}})
        self.sheets.spreadsheets().batchUpdate(spreadsheetId=workbook,body={'requests':requests}).execute()
    def calendar_upsert(self,e,sources):
        if e['status']=='draft':return
        mapping=[r for r in sources.get('CalendarLog',[]) if r.get('EventDraftID')=='board:'+str(e['id']) and r.get('CalendarEventID')]
        if len(mapping)>1:raise ValueError('Duplicate Calendar mapping requires review')
        cid=mapping[0]['CalendarEventID'] if mapping else calendar_id(e['id'])
        api=self.calendar.events()
        try: existing=api.get(calendarId=self.calendar_target,eventId=cid).execute()
        except Exception as ex:
            if getattr(getattr(ex,'resp',None),'status',None) not in {404,410}:raise
            existing=None
        if e['status']=='cancelled':
            if existing and existing.get('status')!='cancelled':api.patch(calendarId=self.calendar_target,eventId=cid,sendUpdates='none',body={'status':'cancelled'}).execute()
            return
        c=e.get('completion') or {}
        body={'summary':e['name']+(' [Completed]' if e['status']=='completed' else ''),'location':e.get('location',''),'description':'Volunteer Board event #'+str(e['id'])+'\nStatus: '+e['status']+ ('\n'+c.get('statement','') if c else ''),'start':{'dateTime':e['startsAt'],'timeZone':e.get('timezone','America/Denver')},'end':{'dateTime':e['endsAt'],'timeZone':e.get('timezone','America/Denver')},'extendedProperties':{'private':{'hermesBoardEventId':str(e['id'])}},'status':'confirmed'}
        if existing:
            if any(existing.get(k)!=v for k,v in body.items()):api.patch(calendarId=self.calendar_target,eventId=cid,sendUpdates='none',body=body).execute()
        else:
            try:api.insert(calendarId=self.calendar_target,sendUpdates='none',body={'id':cid,**body}).execute()
            except Exception as ex:
                if getattr(getattr(ex,'resp',None),'status',None)!=409:raise
                api.patch(calendarId=self.calendar_target,eventId=cid,sendUpdates='none',body=body).execute()
        # Stable deterministic ID is the authoritative mapping. Never append a
        # second CalendarLog machine ledger; compatible pre-existing mappings win.

def run_once(board,google,config,path,force=False):
    tick=time.time()
    if not force and tick<config.get('backoff_until',0):return 'backoff'
    try:
        pending=board.call('pending')['pending']
        if not force and not pending and tick-config.get('last_reconciliation_epoch',0)<300:return 'idle'
        snapshot=board.call('snapshot'); sources=google.sources()
        for event in snapshot['events']:google.calendar_upsert(event,sources)
        google.write_views(config['workbook_id'],member_rows(snapshot,sources,now(),config.get('approved_record_ids',{})))
        if pending:board.call('ack',{'ids':[p['id'] for p in pending]})
        config.update(last_success=now(),last_reconciliation_epoch=tick,status='current',failure_count=0,backoff_until=0)
        save(path,config); return 'current'
    except Exception:
        n=config.get('failure_count',0)+1
        config.update(status='sync pending',last_attempt=now(),failure_count=n,backoff_until=tick+min(3600,30*2**min(n,7)))
        save(path,config)
        try:
            google.write_views(config['workbook_id'],{'Sync Status':[['Status','Last successful sync UTC','Failed attempt UTC'],['Sync pending; authoritative sources remain available',config.get('last_success','Never'),now()]]})
        except Exception:
            pass  # Google itself may be down; prior snapshot explicitly warns to check age.
        # No exception repr: Google errors can include credential URLs or source data.
        raise RuntimeError('Projection failed; authoritative state preserved; retry pending.') from None

def main():
    p=argparse.ArgumentParser(); p.add_argument('--config',type=Path,default=DEFAULT_CONFIG); p.add_argument('--initialize',action='store_true'); p.add_argument('--once',action='store_true'); p.add_argument('--force',action='store_true'); args=p.parse_args()
    with exclusive(args.config.with_suffix('.lock')):
        c=load(args.config) if args.config.exists() else {}
        if args.initialize:
            g=Google()
            if not c.get('workbook_id'):g.initialize(c);save(args.config,c)
            g.protect(c['workbook_id']); c['initialized']=True;save(args.config,c)
            print('Member workbook initialized; permissions remain owner-only.');return
        if not c.get('initialized'):raise RuntimeError('Initialize private projection config first')
        default=args.config.parent/'volunteer-board.json'
        try:
            b=Board(c.get('board_config',str(default)));g=Google()
        except Exception:
            c.update(status='sync pending',last_attempt=now());save(args.config,c)
            raise RuntimeError('Projection dependency unavailable') from None
        print(run_once(b,g,c,args.config,args.force))
if __name__=='__main__':
    try:main()
    except Exception:print('Projection unavailable; inspect sanitized status. No Board writes or SMS performed.',file=sys.stderr);sys.exit(1)
