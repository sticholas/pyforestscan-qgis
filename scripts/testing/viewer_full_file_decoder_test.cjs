/* Verify native allocations are released on success and decode failure. */
const fs = require("node:fs");
const vm = require("node:vm");
const assert = require("node:assert/strict");
const path = require("node:path");

async function check(fail) {
    const allocated = [], freed = [];
    let deleted = 0;
    const runtime = {
        HEAPU8: new Uint8Array(1024),
        _malloc(n) { const p = 32 + allocated.length * 64; allocated.push(p); return p; },
        _free(p) { freed.push(p); },
        LASZip: class {
            open() {}
            getPoint(p) { if (fail) throw Error("decode failed"); runtime.HEAPU8[p] = 7; }
            delete() { deleted++; }
        }
    };
    const context = vm.createContext({
        importScripts() {},
        Uint8Array,
        Copc: {Las: {Header: {parse() { return {pointCount: 2, pointDataRecordLength: 1}; }},
                    PointData: {createLazPerf: async () => runtime}}}
    });
    vm.runInContext(fs.readFileSync(path.join(__dirname, "../../pyforestscan_qgis/viewer/full_file_decoder.js"), "utf8"), context);
    const result = context.Copc.Las.PointData.decompressFile(new Uint8Array([1, 2]));
    if (fail) await assert.rejects(result, /decode failed/);
    else assert.deepEqual(Array.from(await result), [7, 7]);
    assert.equal(deleted, 1);
    assert.deepEqual(freed.sort(), allocated.sort());
}
(async () => {
    await check(false);
    await check(true);
    console.log("Full-file decoder allocation lifecycle passed.");
})().catch(error => { console.error(error); process.exitCode = 1; });
