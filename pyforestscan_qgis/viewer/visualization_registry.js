/* Shared viewer palette and classification registry. */
(function(root) {
    "use strict";
    const classification = {
        0:{label:"Never classified",color:[0.50,0.50,0.50]}, 1:{label:"Unclassified",color:[0.62,0.62,0.62]},
        2:{label:"Ground",color:[0.55,0.32,0.16]}, 3:{label:"Low vegetation",color:[0.32,0.70,0.18]},
        4:{label:"Medium vegetation",color:[0.10,0.55,0.14]}, 5:{label:"High vegetation",color:[0.02,0.34,0.08]},
        6:{label:"Building",color:[0.90,0.55,0.10]}, 7:{label:"Low noise",color:[0.82,0.16,0.56]},
        8:{label:"Key point",color:[0.90,0.10,0.10]}, 9:{label:"Water",color:[0.08,0.35,0.85]},
        12:{label:"Overlap",color:[0.78,0.70,0.08]}, 18:{label:"High noise",color:[0.45,0.08,0.58]}
    };
    const palettes = {
        Viridis:[[0.267,0.005,0.329],[0.128,0.567,0.551],[0.993,0.906,0.144]],
        Turbo:[[0.190,0.071,0.232],[0.276,0.506,0.988],[0.643,0.990,0.235],[0.976,0.518,0.039],[0.480,0.016,0.010]],
        Terrain:[[0.12,0.30,0.16],[0.42,0.62,0.24],[0.83,0.76,0.42],[0.96,0.93,0.78]],
        Grayscale:[[0.04,0.04,0.04],[0.96,0.96,0.96]],
        Heat:[[0.04,0.00,0.10],[0.56,0.00,0.36],[0.96,0.18,0.05],[1.00,0.90,0.20]],
        CoolWarm:[[0.08,0.20,0.70],[0.75,0.86,0.94],[0.96,0.94,0.76],[0.72,0.12,0.10]],
        Forest:[[0.02,0.10,0.08],[0.06,0.38,0.20],[0.42,0.70,0.24],[0.92,0.88,0.38]]
    };
    const categoricalFallback = [[0.12,0.47,0.71],[0.84,0.37,0.16],[0.39,0.64,0.18],[0.63,0.34,0.70],[0.10,0.68,0.62],[0.90,0.60,0.12],[0.35,0.35,0.80],[0.75,0.25,0.30]];
    function fallback(code) { return categoricalFallback[Math.abs(Number(code) || 0) % categoricalFallback.length]; }
    function entry(code) { return classification[Number(code)] || {label:"Class " + code, color:fallback(code)}; }
    function gradient(name, invert) {
        const values = palettes[name] || palettes.Viridis;
        const ordered = invert ? values.slice().reverse() : values;
        return ordered.map((color, index) => [ordered.length === 1 ? 0 : index / (ordered.length - 1), new THREE.Color(...color)]);
    }
    root.PyForestScanVisualization = {classification, palettes, paletteNames:Object.keys(palettes), entry, fallback, gradient};
})(globalThis);
