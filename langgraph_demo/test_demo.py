import json
import tempfile
import unittest
from pathlib import Path
from demo import workflow, resume

class DemoTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name); self.db=self.base/'checkpoints.sqlite'
        folder=self.base/'agentic_simulation/claims'; folder.mkdir(parents=True)
        (folder/'claims.json').write_text(json.dumps([{'claim_id':'CLM-1','member_id':'M1','plan':'Synthetic'}]))
        (folder/'audit_trails.json').write_text(json.dumps([{'claim_id':'CLM-1','final_status':'PENDING_REVIEW',
            'stages':[{'status':'PENDING','note':'Requires prior auth review'}]}]))
        refs=self.base/'agentic_reference/data'; refs.mkdir(parents=True)
        (refs/'public_reference.json').write_text(json.dumps([{'text':'Ask the provider for assistance.',
            'metadata':{'visibility':'public','topic':'prior_authorization'},
            'source':{'title':'Reference','url':'https://www.geha.com/'}}]))
        self.cfg={'configurable':{'thread_id':'test'}}

    def start(self,g,actor='member'):
        return g.invoke({'claim_id':'CLM-1','actor':actor},self.cfg)

    def test_restart_and_approve(self):
        with workflow(self.db,self.base) as g:
            self.start(g)
            self.assertEqual(g.get_state(self.cfg).next,('review',))
            self.assertFalse(g.get_state(self.cfg).values['answer'])
        with workflow(self.db,self.base) as g:
            result=resume(g,'test','approve','Checked against source')
            self.assertIn('PENDING_REVIEW',result['answer'])
            self.assertIn('https://www.geha.com/',result['answer'])
            self.assertFalse(g.get_state(self.cfg).next)
            self.assertGreater(len(list(g.get_state_history(self.cfg))),5)
            with self.assertRaises(ValueError): resume(g,'test','approve','Again')

    def test_denied_without_claim_leak(self):
        with workflow(self.db,self.base) as g:
            result=self.start(g,'outsider')
            self.assertNotIn('facts',result)
            self.assertNotIn('draft',result)
            self.assertFalse(g.get_state(self.cfg).next)

    def test_reject(self):
        with workflow(self.db,self.base) as g:
            self.start(g)
            result=resume(g,'test','reject','Needs better evidence')
            self.assertEqual(result['answer'],'Explanation rejected; no response released.')

    def test_edit_and_review_permissions(self):
        with workflow(self.db,self.base) as g:
            self.start(g)
            with self.assertRaises(ValueError): resume(g,'test','approve','Reason',reviewer='member')
            with self.assertRaises(ValueError): resume(g,'test','approve',' ')
            result=resume(g,'test','approve','Edited wording',edited_text='Reviewed explanation')
            self.assertEqual(result['answer'],'Reviewed explanation')

if __name__=='__main__': unittest.main()
