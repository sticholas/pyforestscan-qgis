import unittest
from pyforestscan_qgis.core.active_job import ActiveProcessingJobController,CurrentJobToken

class CurrentJobIsolationTests(unittest.TestCase):
    def token(self,name):return CurrentJobToken('project','session',name,'attempt','plan-'+name,'repo','polygon-'+name,'now')
    def test_new_job_clears_current_and_moves_previous_to_history(self):
        controller=ActiveProcessingJobController();a=self.token('A');b=self.token('B')
        controller.begin(a);controller.update(a,'complete',('a.tif',));controller.begin(b)
        self.assertEqual(controller.current.token,b);self.assertEqual(controller.history[0].token,a);self.assertEqual(controller.current.final_output_paths,())
    def test_late_historical_callback_cannot_mutate_or_load(self):
        controller=ActiveProcessingJobController();a=self.token('A');b=self.token('B')
        controller.begin(a);controller.update(a,'complete',('a.tif',));controller.begin(b)
        self.assertFalse(controller.update(a,'complete',('late-a.tif',)));self.assertEqual(controller.current.token,b)
        self.assertEqual(controller.current_output_paths(a,('a.tif',)),())
    def test_exactly_current_terminal_outputs_are_accepted(self):
        controller=ActiveProcessingJobController();b=self.token('B');controller.begin(b);controller.update(b,'complete',('b.tif',))
        self.assertEqual(controller.current_output_paths(b,('a.tif','b.tif')),('b.tif',))
    def test_failed_current_job_never_exposes_partial_auto_load_paths(self):
        controller=ActiveProcessingJobController();a=self.token('A');controller.begin(a);controller.update(a,'failed',('partial.tif',))
        self.assertEqual(controller.current_output_paths(a,('partial.tif',)),())
    def test_second_process_click_is_blocked(self):
        controller=ActiveProcessingJobController();controller.begin(self.token('A'))
        with self.assertRaisesRegex(RuntimeError,'already running'):controller.begin(self.token('B'))
    def test_clear_archives_current(self):
        controller=ActiveProcessingJobController();a=self.token('A');controller.begin(a);controller.update(a,'complete',('a.tif',));controller.clear_current()
        self.assertIsNone(controller.current);self.assertEqual(controller.history[0].token,a)
    def test_historical_recovery_is_explicit(self):
        controller=ActiveProcessingJobController();a=self.token('A');b=self.token('B')
        controller.begin(a);controller.update(a,'failed');controller.begin(b);controller.update(b,'complete')
        restored=controller.make_current_and_continue('A');self.assertEqual(restored.token,a)

if __name__=='__main__':unittest.main()
