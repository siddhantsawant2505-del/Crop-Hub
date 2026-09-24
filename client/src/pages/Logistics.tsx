import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { MapPin, Truck, TrendingUp, Star, Navigation, IndianRupee, Loader2, Wheat, ChevronRight, CheckCircle2, Phone, User, Clock, Map as MapIcon, ExternalLink } from "lucide-react";
import { Map, Marker, ZoomControl } from "pigeon-maps";
import { useLocation, useNavigate } from "react-router-dom";

const fadeUp = { hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0, transition: { duration: 0.45 } } };

// ── Types ────────────────────────────────────────────────────────────────────
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
}

interface FeeBreakdown {
  modal_price_per_qtl: number;
  transport_cost_per_qtl: number;
  mandi_rent_per_qtl: number;
  commission_per_qtl: number;
  loading_unloading_per_qtl: number;
  misc_fees_per_qtl: number;
  total_deductions_per_qtl: number;
  net_price_per_qtl: number;
}

interface MandiContact {
  phone?: string;
  alternate_phone?: string;
  secretary_name?: string;
  address: string;
  timings: string;
  helpline?: string;
}

interface MandiInfo {
  id: string;
  name: string;
  lat: number;
  lon: number;
  state: string;
  district: string;
  type: string;
  contact: MandiContact;
}

interface MandiResult {
  mandi: MandiInfo;
  distance_km: number;
  estimated_road_km: number;
  drive_time_min: number;
  modal_price_per_qtl: number;
  fee_breakdown: FeeBreakdown;
  gross_revenue: number;
  total_deductions: number;
  net_revenue: number;
  cultivation_cost: number;
  true_net_profit: number;
  profit_per_qtl: number;
  best: boolean;
  rank: number;
  why_best?: string;
}

interface CropOptimizationResult {
  crop: string;
  icon: string;
  color: string;
  quantity_qtl: number;
  mandis: MandiResult[];
  best_mandi_name: string;
  best_net_profit: number;
}

interface OptimizeResponse {
  lat: number;
  lon: number;
  radius_km: number;
  quantity_qtl: number;
  results: CropOptimizationResult[];
  overall_best_crop: string;
  overall_best_mandi: string;
}

function fmt(n: number) { return "₹" + n.toLocaleString("en-IN", { maximumFractionDigits: 0 }); }

// ── Main Component ───────────────────────────────────────────────────────────
export default function Logistics() {
  const { state } = useLocation();
  const navigate = useNavigate();
  
  // Data passed from Fathom Layer
  const fathomResult: FathomResult | null = state?.fathomResult || null;

  // Form State
  const [lat, setLat] = useState<number | null>(state?.lat || null);
  const [lon, setLon] = useState<number | null>(state?.lon || null);
  const [locLoading, setLocLoading] = useState(false);
  const [radiusKm, setRadiusKm] = useState("150");
  const [quantityQtl, setQuantityQtl] = useState("20");

  // API State
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<OptimizeResponse | null>(null);

  // UI State
  const [activeTab, setActiveTab] = useState<string | null>(null);
  const [selectedMandi, setSelectedMandi] = useState<MandiResult | null>(null);

  useEffect(() => {
    // If no fathom result, redirect or handle graceful empty state.
    if (!fathomResult) {
       // Just showing empty state for now.
    }
  }, [fathomResult]);

  useEffect(() => {
     if (response && response.results.length > 0 && !activeTab) {
         setActiveTab(response.results[0].crop);
     }
  }, [response, activeTab]);

  const getLocation = () => {
    setLocLoading(true);
    if ("geolocation" in navigator) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          setLat(position.coords.latitude);
          setLon(position.coords.longitude);
          setLocLoading(false);
        },
        (err) => {
          console.error(err);
          setLocLoading(false);
          // Fallback to central India if location denied
          setLat(21.1458);
          setLon(79.0882); 
          alert("Location denied or unavailable. Using default coordinates.");
        }
      );
    } else {
      setLocLoading(false);
      alert("Geolocation is not supported by your browser.");
    }
  };

  const handleOptimize = async () => {
    if (!fathomResult || fathomResult.allocations.length === 0) {
      setError("No crop allocations found from Fathom Layer. Please run the Fathom optimizer first.");
      return;
    }
    if (lat === null || lon === null) {
      setError("Please detect your GPS location first.");
      return;
    }
    
    setLoading(true);
    setError(null);
    setSelectedMandi(null);

    try {
      const res = await fetch("http://localhost:5000/api/logistics/optimize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          lat,
          lon,
          allocations: fathomResult.allocations,
          quantity_qtl: parseFloat(quantityQtl),
          radius_km: parseFloat(radiusKm),
        })
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.message || "Failed to optimize logistics");
      }

      setResponse(data.data);
      if (data.data.results.length > 0) {
        setActiveTab(data.data.results[0].crop);
      }
    } catch (err: any) {
      console.error(err);
      setError(err.message || "An unexpected error occurred.");
    } finally {
      setLoading(false);
    }
  };

  const handleOpenGoogleMaps = (lat: number, lon: number) => {
    const url = `https://www.google.com/maps/search/?api=1&query=${lat},${lon}`;
    window.open(url, "_blank");
  };

  const activeCropResult = response?.results.find(r => r.crop === activeTab);

  return (
    <motion.div initial="hidden" animate="show" variants={{ show: { transition: { staggerChildren: 0.08 } } }} className="space-y-6 pb-20">
      
      {/* Header */}
      <motion.div variants={fadeUp}>
        <div className="flex items-center gap-3 mb-1">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center"
            style={{ background: "rgba(196,154,108,0.1)", border: "1px solid rgba(196,154,108,0.2)" }}>
            <Truck className="w-4 h-4" style={{ color: "#c49a6c" }} />
          </div>
          <h1 className="text-3xl font-outfit font-black" style={{ color: "rgb(var(--on-surface))" }}>Logistics & Arbitrage</h1>
        </div>
        <p className="text-sm ml-11" style={{ color: "rgba(186,203,186,0.6)" }}>
           Find the most profitable market for your Fathom Layer crop mix
        </p>
      </motion.div>

      {/* Input Section */}
      <motion.div variants={fadeUp} className="rounded-2xl p-5" style={{ background: "rgb(var(--surface-container))", border: "1px solid rgba(0,232,122,0.08)" }}>
         {!fathomResult ? (
            <div className="text-center py-6">
                <Wheat className="w-10 h-10 mx-auto mb-3 opacity-30" style={{ color: "#ffb955" }} />
                <p className="text-sm mb-4" style={{ color: "rgba(186,203,186,0.6)" }}>
                   You need a crop mix to run logistics optimization.
                </p>
                <button onClick={() => navigate("/fathom")} className="px-4 py-2 rounded-lg bg-white/5 text-sm font-semibold hover:bg-white/10 transition">
                   Go to Fathom Layer
                </button>
            </div>
         ) : (
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
               <div>
                  <label className="block text-xs font-semibold uppercase tracking-widest mb-2" style={{ color: "rgba(186,203,186,0.5)" }}>Your Location</label>
                  <button 
                     onClick={getLocation}
                     disabled={locLoading}
                     className="w-full h-12 rounded-xl flex items-center justify-center gap-2 text-sm font-semibold border transition hover:bg-white/5"
                     style={{ borderColor: lat ? "rgba(0,232,122,0.3)" : "rgba(255,255,255,0.1)", color: lat ? "#00e87a" : "white" }}>
                     {locLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <MapPin className="w-4 h-4" />}
                     {lat ? `${lat.toFixed(2)}, ${lon?.toFixed(2)}` : "Detect GPS"}
                  </button>
               </div>
               <div>
                  <label className="block text-xs font-semibold uppercase tracking-widest mb-2" style={{ color: "rgba(186,203,186,0.5)" }}>Quantity per Crop</label>
                  <div className="flex items-center gap-2 h-12 rounded-xl px-4 border border-white/10 bg-black/20 focus-within:border-white/30">
                     <input type="number" value={quantityQtl} onChange={e => setQuantityQtl(e.target.value)} 
                        className="bg-transparent w-full outline-none font-mono text-lg" />
                     <span className="text-xs font-semibold opacity-50">QTL</span>
                  </div>
               </div>
               <div>
                  <label className="block text-xs font-semibold uppercase tracking-widest mb-2" style={{ color: "rgba(186,203,186,0.5)" }}>Search Radius</label>
                  <div className="flex items-center gap-2 h-12 rounded-xl px-4 border border-white/10 bg-black/20 focus-within:border-white/30">
                     <input type="number" value={radiusKm} onChange={e => setRadiusKm(e.target.value)} 
                        className="bg-transparent w-full outline-none font-mono text-lg" />
                     <span className="text-xs font-semibold opacity-50">KM</span>
                  </div>
               </div>
               <button 
                  onClick={handleOptimize}
                  disabled={loading || !lat}
                  className="h-12 rounded-xl flex items-center justify-center gap-2 text-sm font-black transition-all disabled:opacity-50"
                  style={{ background: "linear-gradient(to right, #00e87a, #00c165)", color: "#000", boxShadow: "0 0 15px rgba(0,232,122,0.15)" }}>
                  {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : "Optimize Mandis"}
               </button>
            </div>
         )}
      </motion.div>

      {error && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-red-400 p-4 border border-red-500/20 bg-red-500/10 rounded-xl text-sm">
          {error}
        </motion.div>
      )}

      {/* Results Section */}
      {response && activeCropResult && (
         <motion.div variants={fadeUp} className="space-y-6">
            
            {/* Crop Tabs */}
            <div className="flex overflow-x-auto gap-2 pb-2 hide-scrollbar">
               {response.results.map(c => (
                  <button key={c.crop} onClick={() => { setActiveTab(c.crop); setSelectedMandi(null); }}
                     className="px-4 py-2 rounded-xl flex items-center gap-2 text-sm font-semibold transition whitespace-nowrap border border-transparent"
                     style={{ 
                        background: activeTab === c.crop ? `${c.color}20` : "rgb(var(--surface-container))",
                        borderColor: activeTab === c.crop ? `${c.color}50` : "rgba(255,255,255,0.05)",
                        color: activeTab === c.crop ? c.color : "rgba(255,255,255,0.7)"
                     }}>
                     <span>{c.icon}</span> {c.crop}
                  </button>
               ))}
            </div>

            {/* SVG Map & Overview */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
               {/* Map */}
               <div className="lg:col-span-2 rounded-2xl p-5 relative overflow-hidden"
                  style={{ background: "rgb(var(--surface-container))", border: "1px solid rgba(0,232,122,0.08)" }}>
                  <div className="flex items-center gap-2 mb-4">
                     <Navigation className="w-4 h-4" style={{ color: activeCropResult.color }} />
                     <h2 className="text-sm font-semibold uppercase tracking-wider" style={{ color: "rgba(186,203,186,0.6)" }}>Delivery Routes</h2>
                  </div>
                  
                  <div className="relative w-full h-80 rounded-xl overflow-hidden border border-white/5">
                     <Map 
                        height={320} 
                        center={[lat || 21.1458, lon || 79.0882]} 
                        defaultZoom={7}
                        boxClassname="pigeon-filters"
                     >
                        <ZoomControl />
                        {/* Farm Marker */}
                        {lat && lon && (
                           <Marker 
                              width={40}
                              anchor={[lat, lon]} 
                              color="#ffffff"
                           />
                        )}
                        
                        {/* Mandi Markers */}
                        {activeCropResult.mandis.map((m) => (
                           <Marker 
                              key={m.mandi.id}
                              width={m.best ? 35 : 25}
                              anchor={[m.mandi.lat, m.mandi.lon]} 
                              color={m.best ? "#00e87a" : "#666"}
                              onClick={() => setSelectedMandi(m)}
                           />
                        ))}
                     </Map>
                     
                     <div className="absolute bottom-4 left-4 z-10 flex gap-3">
                        <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-black/80 backdrop-blur-md border border-white/10">
                           <div className="w-2 h-2 rounded-full bg-white" />
                           <span className="text-[10px] font-bold text-white uppercase">Your Farm</span>
                        </div>
                        <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-black/80 backdrop-blur-md border border-white/10">
                           <div className="w-2 h-2 rounded-full bg-emerald-accent" />
                           <span className="text-[10px] font-bold text-white uppercase">Best Mandi</span>
                        </div>
                     </div>
                  </div>
               </div>

               {/* Selected Overview */}
               <div className="rounded-2xl p-5 flex flex-col"
                  style={{ background: `linear-gradient(135deg, ${activeCropResult.color}10, transparent)`, border: `1px solid ${activeCropResult.color}30` }}>
                  
                  {selectedMandi ? (
                     <div className="h-full flex flex-col">
                        <div className="flex items-center gap-2 mb-4">
                           <span className="text-2xl">{activeCropResult.icon}</span>
                           <div>
                              <h3 className="font-bold text-sm text-white">{selectedMandi.mandi.name}</h3>
                              <p className="text-xs opacity-60">Profit Breakdown • {quantityQtl} qtl</p>
                           </div>
                        </div>

                        <div className="space-y-3 text-sm flex-1">
                           <div className="flex justify-between items-center py-1 border-b border-white/5">
                              <span className="opacity-60">Gross Revenue</span>
                              <span className="font-mono text-green-400">+{fmt(selectedMandi.gross_revenue)}</span>
                           </div>
                           <div className="flex justify-between items-center py-1">
                              <span className="opacity-60 text-xs pl-2">Transport</span>
                              <span className="font-mono text-red-400 text-xs">-{fmt(selectedMandi.fee_breakdown.transport_cost_per_qtl * response.quantity_qtl)}</span>
                           </div>
                           <div className="flex justify-between items-center py-1">
                              <span className="opacity-60 text-xs pl-2">Mandi Rent</span>
                              <span className="font-mono text-red-400 text-xs">-{fmt(selectedMandi.fee_breakdown.mandi_rent_per_qtl * response.quantity_qtl)}</span>
                           </div>
                           <div className="flex justify-between items-center py-1">
                              <span className="opacity-60 text-xs pl-2">Commission</span>
                              <span className="font-mono text-red-400 text-xs">-{fmt(selectedMandi.fee_breakdown.commission_per_qtl * response.quantity_qtl)}</span>
                           </div>
                           <div className="flex justify-between items-center py-1 border-b border-white/5 pb-2">
                              <span className="opacity-60 text-xs pl-2">Labor/Misc</span>
                              <span className="font-mono text-red-400 text-xs">-{fmt((selectedMandi.fee_breakdown.loading_unloading_per_qtl + selectedMandi.fee_breakdown.misc_fees_per_qtl) * response.quantity_qtl)}</span>
                           </div>
                           <div className="flex justify-between items-center py-1 font-bold pt-1">
                              <span className="text-white">Net Profit</span>
                              <span className="font-mono text-lg" style={{ color: activeCropResult.color }}>{fmt(selectedMandi.true_net_profit)}</span>
                           </div>
                        </div>

                        <div className="mt-4 p-3 rounded-xl bg-black/20 border border-white/5">
                           <div className="flex items-center gap-2 mb-2">
                              <Phone className="w-3.5 h-3.5 text-white/60" />
                              <span className="text-xs font-semibold">Contact Info</span>
                           </div>
                           {selectedMandi.mandi.contact.phone ? (
                              <p className="font-mono text-sm text-green-400 mb-1">{selectedMandi.mandi.contact.phone}</p>
                           ) : (
                              <p className="text-xs text-white/50 mb-1">No phone available</p>
                           )}
                           <p className="text-[10px] text-white/50 leading-tight">{selectedMandi.mandi.contact.address}</p>
                        </div>
                     </div>
                  ) : (
                     <div className="h-full flex flex-col items-center justify-center text-center opacity-50">
                        <IndianRupee className="w-10 h-10 mb-3" />
                        <p className="text-sm font-semibold">Select a mandi below to view full profit breakdown & contact details.</p>
                     </div>
                  )}
               </div>
            </div>

            {/* Ranked Mandi Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
               {activeCropResult.mandis.map((m, i) => (
                  <motion.div key={m.mandi.id}
                     initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 * i }}
                     onClick={() => setSelectedMandi(m)}
                     className={`rounded-2xl p-4 cursor-pointer transition-all ${selectedMandi?.mandi.id === m.mandi.id ? "ring-2" : "hover:border-white/20"}`}
                     style={{ 
                        background: m.best ? "rgba(0,232,122,0.05)" : "rgb(var(--surface-container))",
                        border: `1px solid ${m.best ? "rgba(0,232,122,0.3)" : "rgba(255,255,255,0.05)"}`,
                        ringColor: activeCropResult.color 
                     }}>
                     
                     <div className="flex justify-between items-start mb-3">
                        <div className="flex items-center gap-2">
                           <div className="w-6 h-6 rounded-full flex items-center justify-center" style={{ background: "rgba(255,255,255,0.1)" }}>
                              <span className="text-[10px] font-black">{m.rank}</span>
                           </div>
                           <div>
                              <h4 className="font-bold text-sm">{m.mandi.name}</h4>
                              <p className="text-[10px] opacity-60 flex items-center gap-1">
                                 <Truck className="w-2.5 h-2.5" /> {m.estimated_road_km.toFixed(0)} km road
                              </p>
                           </div>
                        </div>
                        {m.best && (
                           <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded-full text-green-400 bg-green-400/10 flex items-center gap-1">
                              <Star className="w-2.5 h-2.5 fill-current" /> Best Pick
                           </span>
                        )}
                     </div>

                     <div className="space-y-1.5 mb-4">
                        <div className="flex justify-between text-xs">
                           <span className="opacity-50">Live Price</span>
                           <span className="font-mono text-white/80">{fmt(m.modal_price_per_qtl)}/qtl</span>
                        </div>
                        <div className="flex justify-between text-xs">
                           <span className="opacity-50">Transport</span>
                           <span className="font-mono text-red-400/80">-{fmt(m.fee_breakdown.transport_cost_per_qtl)}/qtl</span>
                        </div>
                        <div className="flex justify-between text-xs">
                           <span className="opacity-50">Fees & Rent</span>
                           <span className="font-mono text-red-400/80">-{fmt(m.fee_breakdown.total_deductions_per_qtl - m.fee_breakdown.transport_cost_per_qtl)}/qtl</span>
                        </div>
                     </div>

                     <div className="pt-3 border-t border-white/5 flex justify-between items-center">
                        <button 
                           onClick={(e) => { e.stopPropagation(); handleOpenGoogleMaps(m.mandi.lat, m.mandi.lon); }}
                           className="flex items-center gap-1.5 px-2 py-1 rounded bg-white/5 hover:bg-white/10 transition text-[9px] font-bold uppercase tracking-wider text-white/60">
                           <ExternalLink className="w-3 h-3" /> Directions
                        </button>
                        <div className="text-right">
                           <p className="text-[10px] font-bold uppercase tracking-wider opacity-50 mb-0.5">True Net Profit</p>
                           <p className="font-mono font-black text-lg" style={{ color: m.best ? "#00e87a" : "white" }}>
                              {fmt(m.true_net_profit)}
                           </p>
                        </div>
                     </div>
                  </motion.div>
               ))}
            </div>

            {/* Comparison Table */}
            <div className="rounded-2xl overflow-hidden" style={{ background: "rgb(var(--surface-container))", border: "1px solid rgba(255,255,255,0.05)" }}>
               <div className="p-4 border-b border-white/5">
                  <h3 className="text-sm font-semibold uppercase tracking-wider opacity-60">Full Market Comparison</h3>
               </div>
               <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                     <thead>
                        <tr className="bg-white/5 text-xs uppercase tracking-wider opacity-60 text-left">
                           <th className="px-5 py-3 font-semibold">Mandi</th>
                           <th className="px-5 py-3 font-semibold">Distance</th>
                           <th className="px-5 py-3 font-semibold">Price/Qtl</th>
                           <th className="px-5 py-3 font-semibold text-red-400">Total Deductions</th>
                           <th className="px-5 py-3 font-semibold text-right text-green-400">Net Profit</th>
                           <th className="px-5 py-3 font-semibold text-right">Actions</th>
                        </tr>
                     </thead>
                     <tbody>
                        {activeCropResult.mandis.map(m => (
                           <tr key={m.mandi.id} className="border-b border-white/5 hover:bg-white/5 transition cursor-pointer"
                               onClick={() => setSelectedMandi(m)}>
                              <td className="px-5 py-4 flex items-center gap-2">
                                 {m.best && <Star className="w-3 h-3 text-green-400 fill-current" />}
                                 <span className={m.best ? "font-bold text-green-400" : ""}>{m.mandi.name}</span>
                              </td>
                              <td className="px-5 py-4 opacity-70 font-mono text-xs">{m.estimated_road_km.toFixed(0)} km</td>
                              <td className="px-5 py-4 opacity-70 font-mono text-xs">{fmt(m.modal_price_per_qtl)}</td>
                              <td className="px-5 py-4 text-red-400/80 font-mono text-xs">-{fmt(m.total_deductions)}</td>
                              <td className="px-5 py-4 text-right font-mono font-bold" style={{ color: m.best ? "#00e87a" : "white" }}>
                                 {fmt(m.true_net_profit)}
                              </td>
                              <td className="px-5 py-4 text-right">
                                 <button 
                                    onClick={(e) => { e.stopPropagation(); handleOpenGoogleMaps(m.mandi.lat, m.mandi.lon); }}
                                    className="p-2 rounded-lg bg-white/5 hover:bg-white/10 transition text-white/60 hover:text-white"
                                    title="Open in Google Maps">
                                    <ExternalLink className="w-4 h-4" />
                                 </button>
                              </td>
                           </tr>
                        ))}
                     </tbody>
                  </table>
               </div>
            </div>

         </motion.div>
      )}

    </motion.div>
  );
}
