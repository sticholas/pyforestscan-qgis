import math,tempfile,unittest
from pathlib import Path
import numpy as np
from pyforestscan_qgis.core.localized_rumple import calculate_local_rumple_surface,rumple_patch_extent
from pyforestscan_qgis.core.output_registry import generated_output_for_path
from pyforestscan_qgis.core.product_capabilities import PRODUCT_CAPABILITIES

def upstream_formula(chm,resolution,min_height=None):
 data=np.asarray(chm,dtype=float)
 if min_height is not None:data=np.where(data>=min_height,data,np.nan)
 dx,dy=resolution;z00,z10,z01,z11=data[:-1,:-1],data[1:,:-1],data[:-1,1:],data[1:,1:]
 valid=np.isfinite(z00)&np.isfinite(z10)&np.isfinite(z01)&np.isfinite(z11)
 if not valid.any():return np.nan
 t1=.5*np.sqrt((dy*(z10-z00))**2+(dx*(z01-z00))**2+(dx*dy)**2)
 t2=.5*np.sqrt((dy*(z01-z11))**2+(dx*(z11-z10))**2+(dx*dy)**2)
 return float(np.sum((t1+t2)[valid])/(valid.sum()*dx*dy))

class RumpleScientificTests(unittest.TestCase):
 def assert_scalar(self,chm,res=(1.,1.),min_height=None):
  surface=calculate_local_rumple_surface(chm,res,min_height)
  self.assertAlmostEqual(upstream_formula(chm,res,min_height),surface.aggregate_rumple,places=12)
  self.assertAlmostEqual(surface.aggregate_rumple,float(np.nanmean(surface.values)),places=12)
 def test_flat_is_one(self):
  surface=calculate_local_rumple_surface(np.ones((8,9))*10,(1,1));self.assertTrue(np.allclose(surface.values,1));self.assertEqual(1,surface.aggregate_rumple)
 def test_uniform_plane_analytical_non_square(self):
  rows,cols=np.mgrid[:7,:8];a,b=2.0,-.5;chm=a*rows+b*cols
  surface=calculate_local_rumple_surface(chm,(2.,3.));expected=math.sqrt(1+(a/2.)**2+(b/3.)**2)
  self.assertTrue(np.allclose(surface.values,expected));self.assertAlmostEqual(expected,surface.aggregate_rumple,12)
 def test_corrugation_and_amplitude(self):
  x=np.arange(20);low=np.tile(np.sin(x), (12,1));high=3*low
  self.assertGreater(calculate_local_rumple_surface(low,(1,1)).aggregate_rumple,1)
  self.assertGreater(calculate_local_rumple_surface(high,(1,1)).aggregate_rumple,calculate_local_rumple_surface(low,(1,1)).aggregate_rumple)
 def test_scalar_equivalence_fixtures(self):
  rng=np.random.default_rng(4);base=rng.normal(size=(20,17));smooth=(base+np.roll(base,1,0)+np.roll(base,1,1))/3
  fixtures=[np.ones((4,4)),np.eye(7)*5,smooth,np.sin(np.arange(80).reshape(8,10))]
  for fixture in fixtures:self.assert_scalar(fixture,(1.5,.75))
 def test_nodata_min_height_and_no_support(self):
  data=np.ones((5,5))*5;data[2,2]=np.nan;self.assert_scalar(data,(1,1));self.assert_scalar(data,(1,1),4)
  empty=calculate_local_rumple_surface(np.ones((3,3)),(1,1),min_height=2);self.assertEqual(0,empty.valid_patch_count);self.assertTrue(math.isnan(empty.aggregate_rumple))
 def test_patch_georeferencing(self):
  self.assertEqual((.5,9.5,1.,19.),rumple_patch_extent((0,10,0,20),(1,2)))
  self.assertEqual((3,4),calculate_local_rumple_surface(np.ones((4,5)),(1,1)).values.shape)
 def test_one_cell_halo_tiled_equivalence(self):
  rng=np.random.default_rng(9);chm=rng.normal(size=(13,17));whole=calculate_local_rumple_surface(chm,(1,1)).values
  split=8;left=calculate_local_rumple_surface(chm[:,:split+1],(1,1)).values;right=calculate_local_rumple_surface(chm[:,split:],(1,1)).values
  tiled=np.concatenate((left,right),axis=1);self.assertTrue(np.array_equal(np.isnan(whole),np.isnan(tiled)));self.assertTrue(np.allclose(whole,tiled,equal_nan=True))
 def test_sparse_gap_does_not_fabricate_values(self):
  chm=np.ones((8,8));chm[:,3:5]=np.nan;surface=calculate_local_rumple_surface(chm,(1,1));self.assertTrue(np.isnan(surface.values[:,2:5]).all())
 def test_contract_and_registry_are_raster_primary(self):
  cap=PRODUCT_CAPABILITIES["rumple"];self.assertEqual("raster",cap.output_kind);self.assertFalse(cap.partition_support);self.assertEqual(("chm",),cap.depends_on);self.assertEqual(1,cap.halo_cells)
  with tempfile.TemporaryDirectory() as folder:
   raster=Path(folder)/"rumple.tif";raster.touch();summary=Path(folder)/"rumple_summary.csv";summary.touch()
   self.assertEqual("rumple",generated_output_for_path(raster,job_id="j").product_key)
   self.assertEqual("rumple_summary",generated_output_for_path(summary,job_id="j").product_key)

if __name__=="__main__":unittest.main()
