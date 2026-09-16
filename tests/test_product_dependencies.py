import unittest

from pyforestscan_qgis.core.product_dependencies import resolve_execution_dag
from pyforestscan_qgis.core.types import ProductType


class ProductDependencyTests(unittest.TestCase):
    def test_point_density_has_no_unnecessary_preparation(self):
        self.assertEqual(resolve_execution_dag((ProductType.POINT_DENSITY,)), ("POINT_DENSITY",))

    def test_multiple_hag_products_share_one_preparation(self):
        dag = resolve_execution_dag((ProductType.PAD, ProductType.PAI, ProductType.VOXEL_STAT), dimensions=("X", "Y", "Z"))
        self.assertEqual(dag[:2], ("DTM", "HAG"))
        self.assertEqual(dag.count("HAG"), 1)

    def test_existing_hag_skips_hidden_preparation(self):
        self.assertEqual(resolve_execution_dag((ProductType.VOXEL_STAT,), has_existing_hag=True), ("VOXEL_STAT",))

    def test_voxel_stat_never_injects_chm_dependency(self):
        dag = resolve_execution_dag((ProductType.VOXEL_STAT,), dimensions=("X", "Y", "Z"))
        self.assertNotIn("CHM", dag)
        self.assertIn("HAG", dag)


if __name__ == "__main__":
    unittest.main()
