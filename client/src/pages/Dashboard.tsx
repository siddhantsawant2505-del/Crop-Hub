import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import axios from "axios";
import {
  Cloud, Droplets, Thermometer, Wind, Sprout, TrendingUp,
  AlertTriangle, ArrowUpRight, Layers, BarChart3, Truck,
  FileText, ArrowRight,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { cropApi, marketApi } from "@/lib/api";

const stagger = { hidden: {}, show: { transition: { staggerChildren: 0.08 } } };
const fadeUp = { hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0, transition: { duration: 0.45 } } };

const statusColors: Record<string, string> = {
  Growing:    "#00e87a",
  Planted:    "#ffb955",
  Harvesting: "#00e87a",
};

const quickActions = [
  { label: "Scan Soil",      icon: Layers,    path: "/terra",     color: "#00e87a", bg: "rgba(0, 232, 122, 0.1)" },
  { label: "Plan Budget",    icon: BarChart3,  path: "/fathom",    color: "#ffb955", bg: "rgba(255, 185, 85, 0.1)" },
  { label: "Check Markets",  icon: Truck,      path: "/logistics", color: "#00e87a", bg: "rgba(0, 232, 122, 0.1)" },
  { label: "View Reports",   icon: FileText,   path: "#",          color: "rgba(186, 203, 186, 0.6)", bg: "rgba(255, 255, 255, 0.05)" },
];

export default function Dashboard() {
  const { user } = useAuth();
  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
  const today = new Date().toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" });

  const [weather, setWeather] = useState<any>(null);
  const [plans, setPlans] = useState<any[]>([]);
  const [marketInsights, setMarketInsights] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        setLoading(true);
        // Fetch weather
        const weatherRes = await axios.get("https://api.open-meteo.com/v1/forecast?latitude=18.5204&longitude=73.8567&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,wind_speed_10m&timezone=auto");
        setWeather(weatherRes.data.current);

        // Fetch crop plans
        const plansRes = await cropApi.getPlans();
        if (plansRes.data?.success) {
          setPlans(plansRes.data.data.plans);
        }

        // Fetch market insights
        const marketRes = await marketApi.getAnalyses();
        if (marketRes.data?.success) {
          const analyses = marketRes.data.data.analyses;
          const insights = analyses.slice(0, 3).map((a: any) => `${a.crop} recommendation: ${a.recommendation.action}`);
          setMarketInsights(insights.length > 0 ? insights : ["No recent market insights available"]);
        }
      } catch (err) {
        console.error("Failed to fetch dashboard data", err);
      } finally {
        setLoading(false);
      }
    };

    fetchDashboardData();
  }, []);

  const activeCrops = plans.flatMap(plan => 
    plan.allocations.map((a: any) => ({ 
      n: a.crop, 
      a: a.acres, 
      s: plan.status === 'active' ? 'Growing' : plan.status 
    }))
  ).slice(0, 4);

  const totalProfit = plans.reduce((acc, plan) => acc + (plan.summary?.expectedProfit || 0), 0);
  const budgetUtilized = plans.length > 0 ? Math.min(100, Math.round((plans.reduce((acc, plan) => acc + (plan.summary?.totalCost || 0), 0) / (plans[0].budget || 1)) * 100)) : 0;

  return (
    <motion.div variants={stagger} initial="hidden" animate="show" className="space-y-6 p-1">
      {/* ── Header ── */}
      <motion.div variants={fadeUp} className="flex items-start justify-between">
        <div>
          <p className="text-xs font-mono font-bold text-emerald-accent uppercase tracking-widest mb-1">{today}</p>
          <h1 className="text-4xl font-black tracking-tight text-white font-outfit">
            {greeting}{user?.name ? `, ${user.name.split(" ")[0]}` : ""} 👋
          </h1>
          <p className="text-white/40 mt-1">Here's what's happening on your farm today.</p>
        </div>
        <div className="flex items-center gap-2 px-4 py-2 rounded-xl bg-surface-container-lowest border border-white/5 shadow-xl">
          <span className="flex h-2 w-2 rounded-full bg-emerald-accent animate-pulse" />
          <span className="text-xs font-bold text-white/70 uppercase tracking-wider">Live System Path</span>
        </div>
      </motion.div>

      {/* ── Weather Widget ── */}
      <motion.div variants={fadeUp} className="glass-card rounded-[2rem] p-8 border border-white/5 relative overflow-hidden">
        <div className="absolute top-0 right-0 p-8 opacity-10">
          <Wind className="w-24 h-24 text-emerald-accent" />
        </div>
        <div className="flex items-center justify-between mb-8 relative z-10">
          <h2 className="text-xs font-bold uppercase tracking-[0.2em] text-white/40">Today's Conditions</h2>
          <span className="text-xs text-white/20 font-mono">PUNE, MH • UPDATED 2M AGO</span>
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-8 relative z-10">
          {[
            { icon: Thermometer, label: "Temp", value: weather ? `${weather.temperature_2m}°C` : "--°C", sub: weather ? `Feels like ${weather.apparent_temperature}°C` : "--", color: "#ffb955" },
            { icon: Droplets,    label: "Humidity", value: weather ? `${weather.relative_humidity_2m}%` : "--%",  sub: "Current", color: "#00e87a" },
            { icon: Cloud,       label: "Precip", value: weather ? `${weather.precipitation}mm` : "--mm", sub: "Rainfall", color: "#00e87a" },
            { icon: Wind,        label: "Wind", value: weather ? `${weather.wind_speed_10m}km/h` : "--km/h", sub: "Speed", color: "#00e87a" },
          ].map(({ icon: Icon, label, value, sub, color }) => (
            <div key={label} className="space-y-1">
              <div className="flex items-center gap-2 mb-2">
                <div className="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center">
                  <Icon className="w-4 h-4" style={{ color }} />
                </div>
                <span className="text-xs font-bold text-white/30 uppercase tracking-widest">{label}</span>
              </div>
              <p className="text-3xl font-black text-white font-outfit">{value}</p>
              <p className="text-[10px] font-bold text-white/20 uppercase tracking-wider">{sub}</p>
            </div>
          ))}
        </div>
      </motion.div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <motion.div variants={fadeUp} className="glass-card p-6 rounded-[1.5rem] border border-white/5 relative group">
          <div className="flex items-start justify-between mb-6">
            <div>
              <p className="text-xs font-bold text-white/30 uppercase tracking-widest mb-2 font-mono">Active Plans</p>
              <h3 className="text-5xl font-black text-white font-outfit">{plans.length}</h3>
            </div>
            <div className="w-12 h-12 rounded-2xl bg-emerald-accent/10 flex items-center justify-center border border-emerald-accent/20">
              <Sprout className="w-6 h-6 text-emerald-accent" />
            </div>
          </div>
          <div className="space-y-3">
            {activeCrops.length > 0 ? activeCrops.map((c, i) => (
              <div key={`${c.n}-${i}`} className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-3">
                  <div className={`w-1.5 h-1.5 rounded-full ${c.s==='Growing'?'bg-emerald-accent':'bg-harvest-gold'}`} />
                  <span className="font-bold text-white/80">{c.n}</span>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-xs font-mono text-white/20">{c.a}ac</span>
                  <span className={`text-[10px] font-black uppercase tracking-widest px-2 py-0.5 rounded-md ${c.s==='Growing'?'bg-emerald-accent/10 text-emerald-accent':'bg-harvest-gold/10 text-harvest-gold'}`}>{c.s}</span>
                </div>
              </div>
            )) : <p className="text-sm text-white/40">No active crops</p>}
          </div>
        </motion.div>

        <motion.div variants={fadeUp} className="glass-card p-6 rounded-[1.5rem] border border-white/5 relative group">
          <div className="flex items-start justify-between mb-6">
            <div>
              <p className="text-xs font-bold text-white/30 uppercase tracking-widest mb-2 font-mono">Market Insights</p>
              <h3 className="text-5xl font-black text-white font-outfit">{marketInsights.length}</h3>
            </div>
            <div className="w-12 h-12 rounded-2xl bg-harvest-gold/10 flex items-center justify-center border border-harvest-gold/20">
              <TrendingUp className="w-6 h-6 text-harvest-gold" />
            </div>
          </div>
          <div className="space-y-4">
            {marketInsights.length > 0 ? marketInsights.map((m, i) => (
              <div key={i} className="flex items-center gap-3 text-xs font-medium text-white/60 p-3 rounded-xl bg-white/5 border border-white/5">
                <ArrowUpRight className="w-4 h-4 text-emerald-accent" /> {m}
              </div>
            )) : <p className="text-sm text-white/40">No recent market insights</p>}
          </div>
        </motion.div>

        <motion.div variants={fadeUp} className="glass-card p-6 rounded-[1.5rem] border border-white/10 relative overflow-hidden bg-gradient-to-br from-[#00e87a]/10 to-transparent">
          <div className="flex items-start justify-between mb-4">
            <div>
              <p className="text-xs font-bold text-white/30 uppercase tracking-widest mb-2 font-mono">Season Profit</p>
              <h3 className="text-4xl font-black text-emerald-accent font-outfit">₹{totalProfit.toLocaleString('en-IN')}</h3>
            </div>
            <div className="w-12 h-12 rounded-2xl bg-emerald-accent/20 flex items-center justify-center border border-emerald-accent/30 shadow-lg shadow-glow-green">
              <TrendingUp className="w-6 h-6 text-emerald-accent" />
            </div>
          </div>
          <div className="mt-8 space-y-4">
            <div className="flex justify-between text-xs font-bold uppercase tracking-widest text-white/40">
              <span>Budget Utilized</span>
              <span className="text-emerald-accent">{budgetUtilized}%</span>
            </div>
            <div className="h-2 w-full bg-white/5 rounded-full overflow-hidden border border-white/5">
              <motion.div initial={{ width: 0 }} animate={{ width: `${budgetUtilized}%` }} transition={{ duration: 1, delay: 0.5 }} className="h-full bg-gradient-to-r from-[#00e87a] to-[#00c860]" />
            </div>
          </div>
        </motion.div>
      </div>

      {/* ── Quick Actions ── */}
      <motion.div variants={fadeUp}>
        <p className="text-xs font-bold text-white/20 uppercase tracking-[0.2em] mb-4 font-mono">Quick Actions</p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {quickActions.map(({ label, icon: Icon, path, color, bg }) => (
            <Link key={label} to={path} className="glass-card flex items-center justify-between p-5 rounded-2xl border border-white/5 hover:border-white/20 transition-all group overflow-hidden relative">
              <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/5 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-1000" />
              <div className="flex items-center gap-4 relative z-10">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0" style={{ background: bg }}>
                  <Icon className="w-5 h-5" style={{ color }} />
                </div>
                <span className="text-sm font-bold text-white tracking-wide">{label}</span>
              </div>
              <ArrowRight className="w-4 h-4 text-white/20 group-hover:text-emerald-accent group-hover:translate-x-1 transition-all relative z-10" />
            </Link>
          ))}
        </div>
      </motion.div>
    </motion.div>
  );
}
