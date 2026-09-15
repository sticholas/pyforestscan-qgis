const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(require("path").join(__dirname, "../../pyforestscan_qgis/viewer/rgb.js"), "utf8");
const context = { module: { exports: {} }, globalThis: {} };
vm.runInNewContext(source, context);
const RGBStats = context.module.exports.RGBStats;
function check(condition, message) {
  if (!condition) throw new Error(message);
}
function report(values, present = true) {
  const stats = new RGBStats(present);
  values.forEach(([r, g, b]) => stats.add(r, g, b));
  return stats.report();
}
const valid8 = report([[0, 20, 255], [255, 10, 1]]);
check(valid8.status === "RGB_AVAILABLE_VALID", "8-bit valid fixture");
check(valid8.display_transform.divisor === 1, "8-bit divisor");
const valid16 = report([[0, 2000, 65535], [65535, 1024, 10]]);
check(valid16.status === "RGB_AVAILABLE_VALID", "16-bit valid fixture");
check(valid16.display_transform.divisor === 256, "16-bit divisor");
check(report([[0, 0, 0], [0, 0, 0]]).status === "RGB_AVAILABLE_ALL_ZERO", "all-zero fixture");
check(report([[10, 10, 10], [10, 10, 10]]).status === "RGB_AVAILABLE_CONSTANT", "constant fixture");
check(report([[10, -1, 20], [10, 10, 10]]).status === "RGB_PARTIAL", "invalid fixture");
check(report([[1, 2, 3]], false).status === "RGB_MISSING", "missing-channel fixture");
const payload = report([[5, 6, 7]]);
check(payload.source_modified === undefined || payload.display_transform.source_modified === false, "source immutability");
console.log("RGB qualification fixtures passed");
