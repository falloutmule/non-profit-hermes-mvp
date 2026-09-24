import importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
p=Path(__file__).resolve().parents[1]/'scripts/member_operations_projection.py'
spec=importlib.util.spec_from_file_location('projection',p); m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def snapshot():
 return {'events':[{'id':1,'name':'Pantry','status':'draft','capacity':6,'startsAt':'2026-09-26T21:45:00Z','endsAt':'2026-09-26T23:00:00Z','location':'Venue','description':'PRIVATE TEXT','confirmedCount':1,'standbyCount':1,'reservedCount':1,'spotsAvailable':4}], 'staffing':[{'id':4,'eventId':1,'volunteerId':7,'status':'confirmed','phone':'PRIVATE PHONE'}], 'activity':[{'id':1,'createdAt':'now','source':'sms','action':'signup.created','target':'signup:4','result':'success','body':'PRIVATE SMS'}],'generatedAt':'now'}

class Tests(unittest.TestCase):
 def test_projection_allowlist(self):
  rows=m.member_rows(snapshot(),{},'now'); text=json.dumps(rows)
  self.assertNotIn('PRIVATE',text);self.assertIn('Volunteer #7',text);self.assertIn('MDT',text)
 def test_privacy_gate_and_no_donor(self):
  sources={'Donations':[{'DonationID':'D1','DonorContact':'SECRET','DonorName':'SECRET','PrivacyLevel':'public-safe','PublicListingAllowed':'yes','DonationType':'food'},{'DonationID':'D2','PrivacyLevel':'private','PublicListingAllowed':'yes'}], 'Reports':[{'ReportID':'R','PrivacyLevel':'public-safe','PublicSummaryAllowed':'yes','Summary':'SECRET','SensitiveDetails':'SECRET','PublicSummaryDraft':'Approved summary'}], 'Tasks':[{'TaskID':'T','TaskTitle':'SECRET'}]}
  rows=m.member_rows(snapshot(),sources,'now')
  self.assertEqual(len(rows['Donations Summary']),2);self.assertEqual(len(rows['Tasks']),1);self.assertNotIn('SECRET',json.dumps(rows));self.assertIn('Approved summary',json.dumps(rows))
 def test_public_need_gate(self):
  rows=m.member_rows(snapshot(),{'Requests':[{'RequestID':'1','PrivacyLevel':'public-safe','ConsentToShare':'no'},{'RequestID':'2','PrivacyLevel':'public-safe','ConsentToShare':'yes'}],'Inventory':[{'ItemID':'3','PublicNeedAllowed':'yes','Notes':'SECRET'}]},'now')
  self.assertEqual(len(rows['Needs']),3); self.assertEqual(len(rows['Inventory']),2);self.assertNotIn('SECRET',json.dumps(rows))
 def test_member_authorization_not_public_publication(self):
  sources={'Tasks':[{'TaskID':'T','TaskTitle':'Reviewed title'},{'TaskID':'P','TaskTitle':'SECRET','PrivacyLevel':'private-review'}], 'Inventory':[{'ItemID':'I','ItemName':'Socks','PublicNeedAllowed':'no'},{'ItemID':'P','ItemName':'SECRET','PrivacyLevel':'private'}]}
  rows=m.member_rows(snapshot(),sources,'now',{'Tasks':['T','P']})
  self.assertIn('Reviewed title',json.dumps(rows));self.assertIn('Socks',json.dumps(rows));self.assertNotIn('SECRET',json.dumps(rows))
 def test_legacy_audit_prefixed_private_and_ambiguous_targets(self):
  sources={'Requests':[{'RequestID':'R1','PrivacyLevel':'board-visible'},{'RequestID':'PRIVATE','PrivacyLevel':'private-review'},{'RequestID':'SHARED','PrivacyLevel':'board-visible'}], 'Inventory':[{'ItemID':'I1','ItemName':'Socks'}], 'Tasks':[{'TaskID':'SHARED','TaskTitle':'PRIVATE'}]}
  refs=['Requests/R1','Inventory/I1','R1','Requests/PRIVATE','PRIVATE','SHARED','Tasks/SHARED','Requests/SHARED']
  sources['AuditLog']=[{'AuditID':str(i),'Timestamp':'now','Action':'create','TargetItem':ref,'Before':'SECRET','After':'SECRET','Actor':'SECRET'} for i,ref in enumerate(refs)]
  rows=m.member_rows(snapshot(),sources,'now')['Activity'][1:]
  projected=[r[4] for r in rows if str(r[0]).startswith('google:')]
  self.assertEqual(projected,['Requests/R1','Inventory/I1','R1','Requests/SHARED'])
  self.assertNotIn('SECRET',json.dumps(rows))
 def test_duplicate_source_id_does_not_expose_ambiguous_audit(self):
  sources={'Requests':[{'RequestID':'R','PrivacyLevel':'board-visible'},{'RequestID':'R','PrivacyLevel':'private-review'}], 'AuditLog':[{'AuditID':'A','TargetItem':'Requests/R','Action':'update'}]}
  rows=m.member_rows(snapshot(),sources,'now')['Activity']
  self.assertFalse(any(str(r[0]).startswith('google:') for r in rows))
 def test_completion(self):
  s=snapshot();s['events'][0]['completion']={'volunteerId':7,'completedAt':'now','statement':'Socks picked up'}
  text=json.dumps(m.member_rows(s,{},'now'));self.assertIn('Socks picked up',text);self.assertIn('Volunteer #7',text)
 def test_google_failure_does_not_ack(self):
  with tempfile.TemporaryDirectory() as d:
   b=Mock();b.call.side_effect=lambda route,payload=None:{'pending':[{'id':3}]} if route=='pending' else snapshot()
   g=Mock();g.sources.return_value={};g.write_views.side_effect=ValueError('SECRET')
   c={'workbook_id':'test'};path=Path(d)/'state.json'
   with self.assertRaisesRegex(RuntimeError,'retry pending'):m.run_once(b,g,c,path)
   self.assertFalse(any(x.args[0]=='ack' for x in b.call.call_args_list));self.assertNotIn('SECRET',path.read_text());self.assertEqual(c['status'],'sync pending')
 def test_success_ack_after_views_and_repeat(self):
  with tempfile.TemporaryDirectory() as d:
   calls=[];b=Mock();b.call.side_effect=lambda route,payload=None:(calls.append(route) or ({'pending':[{'id':3}]} if route=='pending' else snapshot()))
   g=Mock();g.sources.return_value={};g.write_views.side_effect=lambda *a:calls.append('views')
   c={'workbook_id':'test'}
   for _ in range(2):self.assertEqual(m.run_once(b,g,c,Path(d)/'state.json'),'current')
   self.assertLess(calls.index('views'),calls.index('ack'));self.assertEqual(g.write_views.call_args_list[0].args[1]['Events'],g.write_views.call_args_list[1].args[1]['Events'])
 def test_idle_reconcile_and_backoff(self):
  with tempfile.TemporaryDirectory() as d:
   b=Mock();b.call.return_value={'pending':[]};g=Mock();c={'workbook_id':'test','last_reconciliation_epoch':m.time.time()}
   self.assertEqual(m.run_once(b,g,c,Path(d)/'s'),'idle');g.sources.assert_not_called()
   c['backoff_until']=m.time.time()+100
   self.assertEqual(m.run_once(b,g,c,Path(d)/'s'),'backoff')
 def test_calendar_draft_and_stable_id(self):
  g=object.__new__(m.Google);g.calendar=Mock();g.calendar_target='test'
  g.calendar_upsert(snapshot()['events'][0],{});g.calendar.events.assert_not_called()
  self.assertEqual(m.calendar_id(1),m.calendar_id(1));self.assertNotEqual(m.calendar_id(1),m.calendar_id(2))
 def test_sheet_replace_atomic_and_no_formula(self):
  g=object.__new__(m.Google);g.sheets=Mock()
  g.sheets.spreadsheets().get().execute.return_value={'sheets':[{'properties':{'title':'Events','sheetId':100,'gridProperties':{'rowCount':1000}}}]}
  g.write_views('book',{'Events':[['=IMPORTXML(secret)']]})
  body=g.sheets.spreadsheets().batchUpdate.call_args.kwargs['body']
  self.assertEqual(body['requests'][0]['updateCells']['range'],{'sheetId':100})
  self.assertEqual(body['requests'][0]['updateCells']['rows'][0]['values'][0]['userEnteredValue'],{'stringValue':'=IMPORTXML(secret)'})
 def test_calendar_retry_uses_same_identity_and_no_attendees(self):
  g=object.__new__(m.Google);g.calendar=Mock();g.calendar_target='target'
  e=snapshot()['events'][0];e['status']='published';e['timezone']='America/New_York'
  class Missing(Exception):resp=type('Response',(),{'status':404})()
  g.calendar.events().get().execute.side_effect=Missing()
  for i in range(2):g.calendar_upsert(e,{})
  calls=g.calendar.events().insert.call_args_list
  self.assertEqual(calls[0].kwargs['body']['id'],calls[1].kwargs['body']['id'])
  self.assertEqual(calls[0].kwargs['body']['start']['timeZone'],'America/New_York')
  self.assertEqual(calls[0].kwargs['sendUpdates'],'none');self.assertNotIn('attendees',calls[0].kwargs['body'])
 def test_cancel_missing_calendar_never_creates(self):
  g=object.__new__(m.Google);g.calendar=Mock();g.calendar_target='target'
  e=snapshot()['events'][0];e['status']='cancelled'
  class Missing(Exception):resp=type('Response',(),{'status':404})()
  g.calendar.events().get().execute.side_effect=Missing()
  g.calendar_upsert(e,{});g.calendar.events().insert.assert_not_called()
 def test_status_no_secrets(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'c';m.save(p,{'workbook_id':'abc','token':'SECRET','last_success':'now','status':'current'})
   self.assertNotIn('SECRET',json.dumps(m.inspection_status(p)))
 def test_concurrent_lock(self):
  with tempfile.TemporaryDirectory() as d:
   with m.exclusive(Path(d)/'lock'):
    with self.assertRaises(OSError):
     with m.exclusive(Path(d)/'lock'):pass
if __name__=='__main__':unittest.main()
