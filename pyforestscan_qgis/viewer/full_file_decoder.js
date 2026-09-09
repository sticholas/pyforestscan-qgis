/* Own adapter around the pinned decoder: release full-file WASM allocations. */
importScripts("./EptLaszipDecoderWorker.vendor.js");
importScripts("./rgb.js");
// Piggyback raw color statistics on existing getter calls, before 8-bit conversion.
if (Copc.Las.View) {
    const createView = Copc.Las.View.create;
    const sendMessage = self.postMessage.bind(self);
    let stats;
    Copc.Las.View.create = function(...args) {
        const view = createView(...args);
        stats = new RGBStats(["Red","Green","Blue"].every(name => view.dimensions[name]));
        const getter = view.getter.bind(view), sample = {};
        view.getter = name => {
            const original = getter(name);
            if (!["Red","Green","Blue"].includes(name)) return original;
            return index => {
                const value = original(index);
                sample[name] = value;
                if (name==="Blue") stats.add(sample.Red,sample.Green,value);
                return value;
            };
        };
        return view;
    };
    self.postMessage = function(message, transfer) {
        if (stats && message.gpsMeta) message.gpsMeta.rgbDiagnostic = stats.report();
        return sendMessage(message, transfer);
    };
}
let fullFileRuntime;
Copc.Las.PointData.decompressFile = async function (input) {
    if (!fullFileRuntime) fullFileRuntime = Copc.Las.PointData.createLazPerf();
    const runtime = await fullFileRuntime;
    const header = Copc.Las.Header.parse(input);
    const length = header.pointDataRecordLength;
    const output = new Uint8Array(header.pointCount * length);
    let pointer = 0, point = 0, decoder;
    try {
        pointer = runtime._malloc(input.byteLength);
        point = runtime._malloc(length);
        if (!pointer || !point) throw Error("Not enough memory to decode this view node.");
        runtime.HEAPU8.set(input, pointer);
        decoder = new runtime.LASZip();
        decoder.open(pointer, input.byteLength);
        for (let i = 0; i < header.pointCount; i++) {
            decoder.getPoint(point);
            output.set(new Uint8Array(runtime.HEAPU8.buffer, point, length), i * length);
        }
        return output;
    } finally {
        if (decoder) decoder.delete();
        if (point) runtime._free(point);
        if (pointer) runtime._free(pointer);
    }
};
