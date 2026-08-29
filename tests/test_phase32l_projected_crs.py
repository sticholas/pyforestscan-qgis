import math
import tempfile
import unittest
from pathlib import Path

from pyforestscan_qgis.core.backend.process_env import build_processing_engine_environment
from pyforestscan_qgis.core.ept_spatial_reference import (
    canonical_spatial_reference,
    resolve_ept_spatial_reference,
)
from pyforestscan_qgis.core.polygon_transport import (
    COORDINATE_DOMAIN_INVALID,
    FINITE_COORDINATE_REQUIRED,
    GEOGRAPHIC_LONGITUDE_LATITUDE_RANGE,
    PolygonCoordinateValidationError,
    polygon_execution_input_from_selection,
    wkt_to_geojson_geometry,
)


EPSG_6635_WKT = 'PROJCS["NAD83(PA11) / UTM zone 5N",GEOGCS["NAD83(PA11)",DATUM["NAD83_National_Spatial_Reference_System_PA11",SPHEROID["GRS 1980",6378137,298.257222101,AUTHORITY["EPSG","7019"]],AUTHORITY["EPSG","1117"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","6322"]],PROJECTION["Transverse_Mercator"],PARAMETER["latitude_of_origin",0],PARAMETER["central_meridian",-153],PARAMETER["scale_factor",0.9996],PARAMETER["false_easting",500000],PARAMETER["false_northing",0],UNIT["metre",1,AUTHORITY["EPSG","9001"]],AXIS["Easting",EAST],AXIS["Northing",NORTH],AUTHORITY["EPSG","6635"]]'
PROJECTED_POLYGON = "POLYGON ((196188.631177 2167079.3494, 214143.018468 2167079.3494, 214143.018468 2180976.39619, 196188.631177 2167079.3494))"


class Phase32LProjectedCrsTests(unittest.TestCase):
    def test_exact_ept_metadata_prefers_authoritative_epsg(self):
        resolved = resolve_ept_spatial_reference({"srs": {"authority": "EPSG", "horizontal": 6635, "wkt": EPSG_6635_WKT}})
        self.assertTrue(resolved.valid)
        self.assertTrue(resolved.projected)
        self.assertFalse(resolved.geographic)
        self.assertEqual(resolved.units, "metre")
        self.assertEqual(resolved.authority, "EPSG")
        self.assertEqual(resolved.horizontal_code, "6635")
        self.assertEqual(resolved.authid, "EPSG:6635")
        self.assertEqual(resolved.source, "ept_authority_code")

    def test_nested_geogcs_does_not_override_projected_top_level(self):
        resolved = canonical_spatial_reference(EPSG_6635_WKT)
        self.assertTrue(resolved.projected)
        self.assertFalse(resolved.geographic)

    def test_modern_projected_wkt_remains_projected(self):
        wkt = 'PROJCRS["UTM",BASEGEOGCRS["WGS 84"],CONVERSION["UTM"],CS[Cartesian,2],AXIS["E",east],AXIS["N",north],LENGTHUNIT["metre",1]]'
        resolved = canonical_spatial_reference(wkt)
        self.assertTrue(resolved.projected)
        self.assertFalse(resolved.geographic)

    def test_projected_and_unknown_large_finite_coordinates_pass(self):
        for crs in ("EPSG:6635", "EPSG:32605", ""):
            geometry = wkt_to_geojson_geometry(PROJECTED_POLYGON, crs=crs)
            self.assertEqual(geometry["coordinates"][0][0], [196188.631177, 2167079.3494])

    def test_transformed_transport_uses_destination_crs_and_envelope(self):
        selection = type("Selection", (), {
            "geometry_wkt": "POLYGON ((825580 2167497, 825590 2167497, 825590 2167507, 825580 2167497))",
            "source_crs": "EPSG:3750",
            "processing_crs": "EPSG:3750",
            "area": 50.0,
            "feature_count": 1,
        })()
        transport = polygon_execution_input_from_selection(selection, transformed_wkt=PROJECTED_POLYGON, transformed_crs="EPSG:6635")
        self.assertEqual(transport.source_crs_authid, "EPSG:3750")
        self.assertEqual(transport.processing_crs_authid, "EPSG:6635")
        self.assertEqual(transport.envelope, (196188.631177, 2167079.3494, 214143.018468, 2180976.39619))

    def test_geographic_domain_remains_strict(self):
        valid = "POLYGON ((-155 19, -154 19, -154 20, -155 19))"
        invalid = "POLYGON ((181 20, 179 20, 179 21, 181 20))"
        wkt_to_geojson_geometry(valid, crs="EPSG:4326")
        with self.assertRaises(PolygonCoordinateValidationError) as caught:
            wkt_to_geojson_geometry(invalid, crs="EPSG:4326")
        failure = caught.exception.failure
        self.assertEqual(failure.code, COORDINATE_DOMAIN_INVALID)
        self.assertEqual(failure.rule, GEOGRAPHIC_LONGITUDE_LATITUDE_RANGE)
        self.assertEqual(failure.x, 181.0)
        self.assertEqual(failure.vertex_index, 0)
        self.assertIn("EPSG:4326", str(caught.exception))

    def test_nan_and_infinity_are_geometry_failures_for_all_crs(self):
        for value in ("nan", "inf", "-inf"):
            wkt = f"POLYGON (({value} 20, 1 0, 1 1, {value} 20))"
            with self.assertRaises(PolygonCoordinateValidationError) as caught:
                wkt_to_geojson_geometry(wkt, crs="EPSG:6635")
            self.assertEqual(caught.exception.failure.rule, FINITE_COORDINATE_REQUIRED)

    def test_managed_child_environment_inherits_gdal_proj_and_dll_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            env_root = Path(folder)
            gdal = env_root / "Library" / "share" / "gdal"
            proj = env_root / "Library" / "share" / "proj"
            gdal.mkdir(parents=True)
            proj.mkdir(parents=True)
            (gdal / "gdalvrt.xsd").write_text("x", encoding="utf-8")
            (proj / "proj.db").write_text("x", encoding="utf-8")
            env = build_processing_engine_environment(env_root, "windows", {"PATH": "C:\\Windows\\System32"})
            self.assertEqual(env["GDAL_DATA"], str(gdal))
            self.assertEqual(env["PROJ_DATA"], str(proj))
            self.assertEqual(env["PROJ_LIB"], str(proj))
            path = env.get("PATH", env.get("Path", ""))
            self.assertIn(str(env_root / "Library" / "bin"), path)


if __name__ == "__main__":
    unittest.main()
