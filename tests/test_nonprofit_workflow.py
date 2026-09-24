import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import nonprofit_workflow as w
from volunteer_board_operator import pantry_occurrences

class Fake:
    config={'real_use_review_complete':False}
    def __init__(self): self.writes=[];self.rows=[dict(pantry_occurrences()[0],id=1)]
    def events(self): return self.rows
    def request(self,method,route,payload=None):
        if method!='GET':self.writes.append((method,route,payload));return dict(self.rows[0],**payload)
        if route.endswith('/staffing'):return {'confirmedCount':2,'standbyCount':1,'reservedCount':1,'spotsAvailable':3,'signups':[]}
        if route in ('/health','/ready'):return {'ok':True}
        return self.rows[0]

def test_bare_intake_help_never_calls_legacy(monkeypatch):
    monkeypatch.setattr(w,'legacy_router',lambda:(_ for _ in ()).throw(AssertionError('must not call')))
    for name in w.HELP:assert w.dispatch(name)==w.HELP[name]

def test_board_is_read_first():
    c=Fake()
    for command in ('publish 1','create anything','update 1','pantry prepare'):
        assert 'Use /event' in w.dispatch('board',command,c)
    assert not c.writes

def test_staffing_reservations_are_visible():
    text=w.dispatch('board','show 1',Fake())
    assert 'Confirmed: 2/6' in text and 'Open: 3' in text and 'Pending offers: 1' in text

def test_event_publication_stays_gated():
    c=Fake();assert 'held' in w.dispatch('event','publish 1',c);assert not c.writes

def test_event_edit_uses_same_api():
    c=Fake();w.dispatch('event','update 1 {"capacity": 7}',c)
    assert c.writes==[('PATCH','/api/admin/events/1',{'capacity':7})]

def test_no_raw_error_in_reply(monkeypatch):
    monkeypatch.setattr(w,'legacy_router',lambda:(_ for _ in ()).throw(RuntimeError('secret credentials')))
    assert 'secret credentials' not in w.dispatch('need','new request')

def test_daily_uses_real_counts_and_safe_inventory(monkeypatch):
    import member_operations_projection as p
    class Google:
        def sources(self):return {'Requests':[{'Status':'open','PrivateNotes':'SECRET'}], 'Tasks':[{'Status':'complete'}], 'Inventory':[{'ItemID':'x','ItemName':'Socks','QuantityOnHand':'2','MinimumNeeded':'10','Unit':'pairs'}]}
    monkeypatch.setattr(p,'Google',Google)
    monkeypatch.setattr(w,'inspection_link',lambda:'\nMember operations: example')
    text=w.daily(Fake())
    assert 'Needs: 1 not marked closed' in text
    assert 'Tasks: 0 not marked closed' in text
    assert 'Socks: 2 pairs (minimum 10)' in text
    assert 'SECRET' not in text
    assert 'Volunteer gaps' not in text
