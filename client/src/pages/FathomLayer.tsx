import { useState } from "react";
import { motion } from "framer-motion";
import { useLocation, useNavigate } from "react-router-dom";
import { BarChart3, Wheat, TrendingUp, IndianRupee, Leaf, Loader2, ArrowRight, Truck, Download } from "lucide-react";

const fadeUp = { hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0, transition: { duration: 0.45 } } };

interface CropAllocation {
  crop: string;
  icon: string;
  color: string;
  acres: number;
  cost: number;
  revenue: number;
  profit: number;
  margin_pct: number;
  pct_of_land: number;
  market_price_qtl?: number;
}

interface FathomResult {
  allocations: CropAllocation[];
  total_acres: number;
  total_cost: number;
  total_revenue: number;
  expected_profit: number;
  roi_pct: number;
  soil_type: string;
  soil_quality: number;
  budget_inr: number;
  land_acres: number;
  location_detected?: string;
}

function fmt(n: number) { return "₹" + n.toLocaleString("en-IN", { maximumFractionDigits: 0 }); }

export default function FathomLayer() {
  const { state } = useLocation();
  const navigate = useNavigate();
  
  const [budget, setBudget] = useState("");
  const [landSize, setLandSize] = useState("");
  
  const [soilType] = useState(state?.soil_type || "Alluvial_Soil");
  const [soilQuality] = useState(state?.soil_quality || 85.0);
  const [lat] = useState(state?.lat || null);
  const [lon] = useState(state?.lon || null);

  const [result, setResult] = useState<FathomResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);

  const handleDownloadPDF = async () => {
    if (!result) return;
    setDownloading(true);
    try {
      const res = await fetch("http://localhost:8000/fathom/plan-pdf", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(result)
      });
      if (!res.ok) throw new Error("Failed to generate PDF");
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "CropHub_Fathom_Plan.pdf";
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error(err);
      alert("Error downloading PDF");
    } finally {
      setDownloading(false);
    }
  };

  const handleRecommend = async () => {
    const b = parseFloat(budget);
    const l = parseFloat(landSize);
    
    if (!b || !l || b <= 0 || l <= 0) {
      setError("Please enter valid budget and land size.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const res = await fetch("http://localhost:5000/api/fathom/recommend", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          soil_type: soilType,
          soil_quality: soilQuality,
          land_acres: l,
          budget_inr: b,
          lat,
          lon
        })
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.message || "Failed to fetch recommendation");
      }

      setResult(data.data);
    } catch (err: any) {
      console.error(err);
      setError(err.message || "An unexpected error occurred.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <motion.div initial="hidden" animate="show" variants={{ show: { transition: { staggerChildren: 0.08 } } }} className="space-y-6">
      <motion.div variants={fadeUp}>
        <div className="flex items-center gap-3 mb-1">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center"
            style={{ background: "rgba(255,185,85,0.1)", border: "1px solid rgba(255,185,85,0.2)" }}>
            <BarChart3 className="w-4 h-4" style={{ color: "#ffb955" }} />
          </div>
          <h1 className="text-3xl font-outfit font-black" style={{ color: "rgb(var(--on-surface))" }}>Fathom Layer</h1>
        </div>
        <p className="text-sm ml-11" style={{ color: "rgba(186,203,186,0.6)" }}>
          Predictive Optimization — maximize returns per acre
        </p>
      </motion.div>

      {/* Constraints context from TerraLayer */}
      <motion.div variants={fadeUp} className="flex gap-4">
        <div className="px-4 py-2 rounded-xl border flex items-center gap-2" style={{ background: "rgba(0,232,122,0.05)", borderColor: "rgba(0,232,122,0.2)" }}>
           <span className="text-xs font-semibold text-green-500 uppercase tracking-wider">Terra Input:</span>
           <span className="text-sm font-bold text-white">{soilType.replace("_", " ")}</span>
        </div>
        <div className="px-4 py-2 rounded-xl border flex items-center gap-2" style={{ background: "rgba(0,232,122,0.05)", borderColor: "rgba(0,232,122,0.2)" }}>
           <span className="text-xs font-semibold text-green-500 uppercase tracking-wider">Soil Quality:</span>
           <span className="text-sm font-bold text-white">{soilQuality}/100</span>
        </div>
      </motion.div>

      {/* Inputs */}
      <motion.div variants={fadeUp} className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {[
          { label: "Total Budget", placeholder: "e.g. 200000", prefix: "₹", value: budget, set: setBudget },
          { label: "Land Size", placeholder: "e.g. 15", prefix: "ac", value: landSize, set: setLandSize },
        ].map(({ label, placeholder, prefix, value, set }) => (
          <div key={label} className="rounded-2xl p-5"
            style={{ background: "rgb(var(--surface-container))", border: "1px solid rgba(0,232,122,0.08)" }}>
            <label className="block text-xs font-semibold uppercase tracking-widest mb-3"
              style={{ color: "rgba(186,203,186,0.5)" }}>{label}</label>
            <div className="flex items-center gap-3">
              <span className="text-lg font-bold shrink-0" style={{ color: "rgba(186,203,186,0.4)" }}>{prefix}</span>
              <input type="number" value={value} onChange={(e) => set(e.target.value)} placeholder={placeholder}
                className="flex-1 bg-transparent outline-none font-mono text-2xl font-bold placeholder:opacity-30"
                style={{ color: "rgb(var(--on-surface))" }} />
            </div>
            <div className="mt-3 h-px" style={{ background: "rgba(0,232,122,0.12)" }} />
          </div>
        ))}
        
        <div className="flex items-end pb-1 pb-1">
           <button 
             onClick={handleRecommend}
             disabled={loading}
             className="w-full h-[88px] rounded-2xl flex items-center justify-center gap-2 text-sm font-black transition-all disabled:opacity-50"
             style={{ background: "linear-gradient(to right, #00e87a, #00c165)", color: "#000", boxShadow: "0 0 20px rgba(0,232,122,0.2)" }}>
             {loading ? (
                <> <Loader2 className="w-5 h-5 animate-spin" /> Optimizing... </>
             ) : (
                <> Run Fathom ML <ArrowRight className="w-5 h-5" /> </>
             )}
           </button>
        </div>
      </motion.div>

      {error && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-red-400 p-4 border border-red-500/20 bg-red-500/10 rounded-xl text-sm">
          {error}
        </motion.div>
      )}

      {/* Results */}
      {result && result.allocations.length > 0 && (
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
          
          {/* Stacked bar */}
          <div className="rounded-2xl p-5" style={{ background: "rgb(var(--surface-container))", border: "1px solid rgba(0,232,122,0.08)" }}>
            <div className="flex items-center gap-2 mb-4">
              <Wheat className="w-4 h-4" style={{ color: "#ffb955" }} />
              <h2 className="text-sm font-semibold uppercase tracking-wider" style={{ color: "rgba(186,203,186,0.6)" }}>Crop Allocation Plan ({result.total_acres}/{result.land_acres} ac utilized)</h2>
            </div>
            <div className="h-10 rounded-xl overflow-hidden flex mb-3">
              {result.allocations.map((a, i) => (
                <motion.div key={a.crop} initial={{ width: 0 }}
                  animate={{ width: `${(a.acres / result.land_acres) * 100}%` }}
                  transition={{ duration: 0.8, delay: i * 0.1, ease: "easeOut" }}
                  style={{ background: a.color }} className="h-full flex items-center justify-center">
                  {a.pct_of_land >= 15 && (
                    <span className="text-xs font-mono font-bold text-black/70">{a.acres.toFixed(1)}ac</span>
                  )}
                </motion.div>
              ))}
              {/* Unused land space */}
              {result.land_acres > result.total_acres && (
                 <motion.div 
                    initial={{ width: 0 }}
                    animate={{ width: `${((result.land_acres - result.total_acres) / result.land_acres) * 100}%` }}
                    style={{ background: "rgba(255,255,255,0.05)" }} className="h-full flex items-center border border-dashed border-white/20 justify-center">
                 </motion.div>
              )}
            </div>
            <div className="flex flex-wrap gap-4">
              {result.allocations.map((a) => (
                <div key={a.crop} className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded-sm" style={{ background: a.color }} />
                  <span className="text-xs" style={{ color: "rgba(217,230,220,0.7)" }}>{a.icon} {a.crop}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Allocation cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {result.allocations.map((a, i) => (
              <motion.div key={a.crop}
                initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 + i * 0.1 }}
                className="rounded-2xl p-4"
                style={{ background: "rgb(var(--surface-container))", borderTop: `3px solid ${a.color}`, border: `1px solid rgba(0,232,122,0.06)`, borderTopColor: a.color }}>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <span className="text-lg">{a.icon}</span>
                    <span className="font-semibold text-sm" style={{ color: "rgb(var(--on-surface))" }}>{a.crop}</span>
                  </div>
                  <span className="text-xs font-semibold px-2 py-0.5 rounded-full"
                    style={{ background: `${a.color}18`, color: a.color }}>{a.margin_pct.toFixed(0)}% margin</span>
                </div>
                
                {a.market_price_qtl && (
                  <div className="flex items-center gap-1.5 mb-3 px-2 py-1 rounded bg-white/5 border border-white/10">
                    <TrendingUp className="w-3 h-3 text-green-400" />
                    <span className="text-[10px] font-bold text-green-400/80 uppercase tracking-tighter">Market: ₹{(a.market_price_qtl / 100).toFixed(2)}/kg</span>
                  </div>
                )}
                <div className="space-y-1.5 text-xs">
                  {[
                    { label: "Acres",         val: a.acres.toFixed(1) },
                    { label: "Cost",          val: fmt(a.cost) },
                    { label: "Est. Revenue",  val: fmt(a.revenue), accent: true },
                    { label: "Profit",        val: fmt(a.profit) },
                  ].map(({ label, val, accent }) => (
                    <div key={label} className="flex justify-between">
                      <span style={{ color: "rgba(186,203,186,0.5)" }}>{label}</span>
                      <span className="font-mono font-semibold" style={{ color: accent ? a.color : "rgb(var(--on-surface))" }}>{val}</span>
                    </div>
                  ))}
                </div>
              </motion.div>
            ))}
          </div>

          {/* Summary */}
          <div className="rounded-2xl p-5" style={{ background: "linear-gradient(135deg, rgba(0,232,122,0.06) 0%, rgba(0,232,122,0.02) 100%)", border: "1px solid rgba(0,232,122,0.2)" }}>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-6">
              {[
                { label: "Total Utilized", val: `${result.total_acres.toFixed(1)} ac`, icon: Leaf,          color: "#00e87a" },
                { label: "Total Cost",       val: fmt(result.total_cost),             icon: IndianRupee,   color: "#ffb955" },
                { label: "Est. Revenue",     val: fmt(result.total_revenue),          icon: TrendingUp,    color: "#00e87a" },
                { label: "Expected Profit",  val: fmt(result.expected_profit),           icon: BarChart3,     color: "#00e87a" },
                { label: "Overall ROI",      val: `${result.roi_pct.toFixed(1)}%`,       icon: TrendingUp,    color: "#00e87a" },
              ].map(({ label, val, icon: Icon, color }) => (
                <div key={label}>
                  <div className="flex items-center gap-2 mb-1">
                    <Icon className="w-3.5 h-3.5" style={{ color }} />
                    <p className="text-xs font-semibold uppercase tracking-wider" style={{ color: "rgba(186,203,186,0.5)" }}>{label}</p>
                  </div>
                  <p className="font-mono text-xl font-black" style={{ color }}>{val}</p>
                </div>
              ))}
            </div>
            {result.location_detected && (
              <div className="mt-4 pt-4 border-t border-white/5 flex items-center gap-2">
                <span className="text-[10px] uppercase font-bold text-white/30 tracking-[0.2em]">Price Data Origin:</span>
                <span className="text-[10px] font-bold text-green-400/60">{result.location_detected}</span>
              </div>
            )}

            <div className="mt-6 flex justify-end gap-4">
              <button 
                onClick={handleDownloadPDF}
                disabled={downloading}
                className="px-6 py-3 rounded-xl flex items-center gap-3 text-sm font-black transition-all hover:scale-[1.02] active:scale-[0.98] border border-white/20 disabled:opacity-50"
                style={{ 
                  background: "rgba(255,255,255,0.05)", 
                  color: "rgb(var(--on-surface))"
                }}>
                {downloading ? "Generating..." : "Download PDF"}
                <Download className="w-4 h-4" />
              </button>
              <button 
                onClick={() => navigate("/logistics", { state: { fathomResult: result, lat, lon } })}
                className="px-6 py-3 rounded-xl flex items-center gap-3 text-sm font-black transition-all hover:scale-[1.02] active:scale-[0.98]"
                style={{ 
                  background: "rgb(var(--on-surface))", 
                  color: "rgb(var(--surface-container))",
                  boxShadow: "0 10px 30px -10px rgba(0,0,0,0.5)"
                }}>
                Proceed to Logistics Plan
                <Truck className="w-4 h-4" />
              </button>
            </div>
          </div>
        </motion.div>
      )}

      {/* Empty State */}
      {!result && !loading && !error && (
        <motion.div variants={fadeUp} className="rounded-2xl p-8 text-center"
          style={{ background: "rgb(var(--surface-container))", border: "1px dashed rgba(0,232,122,0.15)" }}>
          <BarChart3 className="w-10 h-10 mx-auto mb-3 opacity-30" style={{ color: "#ffb955" }} />
          <p className="text-sm" style={{ color: "rgba(186,203,186,0.5)" }}>Enter your budget and land size to generate an AI allocation plan.</p>
        </motion.div>
      )}
    </motion.div>
  );
}
