/* Bounded statistics; all transformations describe display, never source edits. */
(function(root) {
    "use strict";
    class RGBStats {
        constructor(present = true) {
            this.present = present; this.count = 0; this.invalid = 0;
            this.min = [Infinity, Infinity, Infinity]; this.max = [-Infinity, -Infinity, -Infinity];
        }
        add(r,g,b) {
            if (![r,g,b].every(v => typeof v === "number" && Number.isFinite(v) && v >= 0 && v <= 65535)) {
                this.invalid++; return;
            }
            [r,g,b].forEach((v,i) => { this.min[i]=Math.min(this.min[i],v); this.max[i]=Math.max(this.max[i],v); });
            this.count++;
        }
        merge(other) {
            this.count += other.count || 0; this.invalid += other.invalid || 0;
            if (other.count) for (let i=0;i<3;i++) {
                this.min[i]=Math.min(this.min[i],other.min[i]); this.max[i]=Math.max(this.max[i],other.max[i]);
            }
        }
        report(rendererError = "", domain = "ORIGINAL_RGB") {
            let status, message = "";
            const maximum = this.count ? Math.max(...this.max) : 0;
            const range = this.count ? Math.max(...this.max.map((v,i)=>v-this.min[i])) : 0;
            if (!this.present) { status="RGB_MISSING"; message="RGB is not present in this point cloud."; }
            else if (this.invalid || !this.count) { status="RGB_PARTIAL"; message="RGB sampling is incomplete or includes invalid values."; }
            else if (maximum===0) {
                status="RGB_AVAILABLE_ALL_ZERO";
                message="RGB attributes exist, but the sampled color values are all zero. Classification or Elevation may be more useful.";
            } else if (range===0) { status="RGB_AVAILABLE_CONSTANT"; message="Sampled RGB values are constant; color cannot distinguish these points."; }
            else if (range <= (maximum>255 ? 65535 : 255)*0.02) {
                status="RGB_AVAILABLE_LOW_RANGE"; message="Sampled RGB values have low variation. No contrast stretching is applied.";
            } else status="RGB_AVAILABLE_VALID";
            if (rendererError) {
                message = status==="RGB_AVAILABLE_VALID" || status==="RGB_AVAILABLE_LOW_RANGE" ?
                    "RGB data appears valid, but the viewer could not render it." :
                    "RGB rendering failed; inspect the separate data diagnosis.";
                const data_status=status; status="RGB_RENDER_FAILED";
                return {...this.report("",domain), status, data_status, message, renderer_error:String(rendererError).slice(0,1000)};
            }
            return {status, message, count:this.count, invalid:this.invalid,
                min:this.count?this.min.slice():null, max:this.count?this.max.slice():null, domain,
                scope:"Loaded nodes only; not a whole-source color audit",
                display_transform: domain==="ORIGINAL_RGB" ?
                    {policy:"PINNED_DECODER_PER_NODE", divisor:maximum>255?256:1,
                     encoding:maximum>255?"16_BIT":"8_BIT_OR_EFFECTIVE_8_BIT",
                     channel_offset:0, source_modified:false} :
                    {policy:"ALREADY_DECODED_8_BIT", source_modified:false}};
        }
    }
    root.RGBStats=RGBStats;
    if(typeof module!=="undefined") module.exports={RGBStats};
})(globalThis);
