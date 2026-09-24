import { useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { motion } from "framer-motion";
import { Sprout, Mail, Lock, Eye, EyeOff, ArrowRight, Zap, Shield, TrendingUp } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { useAuth, getApiError } from "@/context/AuthContext";

const highlights = [
  { icon: Zap, text: "AI soil analysis in seconds" },
  { icon: TrendingUp, text: "Predictive crop planning" },
  { icon: Shield, text: "Real-time market arbitrage" },
];

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [showPassword, setShowPassword] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || "/dashboard";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await login(email, password, remember);
      navigate(from, { replace: true });
    } catch (err) {
      setError(getApiError(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex" style={{ background: "rgb(var(--surface))" }}>
      {/* ── Left branding panel ── */}
      <div className="hidden lg:flex lg:w-1/2 relative overflow-hidden items-center justify-center border-r border-white/5" style={{ background: "rgb(var(--surface-container-lowest))" }}>
        {/* Aurora blobs */}
        <div className="absolute inset-0 pointer-events-none overflow-hidden">
          <motion.div animate={{ scale: [1, 1.2, 1], opacity: [0.15, 0.3, 0.15] }}
            transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
            className="absolute -top-32 -left-32 w-[500px] h-[500px] rounded-full blur-[100px]" style={{ background: "rgba(0,232,122,0.10)" }} />
          <motion.div animate={{ scale: [1, 1.15, 1], opacity: [0.1, 0.2, 0.1] }}
            transition={{ duration: 12, repeat: Infinity, ease: "easeInOut", delay: 4 }}
            className="absolute bottom-0 right-0 w-[400px] h-[400px] rounded-full blur-[100px]" style={{ background: "rgba(255,185,85,0.05)" }} />
        </div>
        {/* Grid */}
        <div className="absolute inset-0 opacity-[0.03]" style={{
          backgroundImage: "linear-gradient(var(--emerald-accent) 1px, transparent 1px), linear-gradient(90deg, var(--emerald-accent) 1px, transparent 1px)",
          backgroundSize: "48px 48px",
        }} />
        {/* Content */}
        <div className="relative z-10 max-w-sm px-12">
          <div className="flex items-center gap-4 mb-12">
            <div className="w-12 h-12 rounded-2xl flex items-center justify-center border" style={{ background: "rgba(0,232,122,0.10)", borderColor: "rgba(0,232,122,0.20)", boxShadow: "0 4px 20px rgba(0,232,122,0.10)" }}>
              <Sprout className="w-6 h-6" style={{ color: "var(--emerald-accent)" }} />
            </div>
            <span className="text-2xl font-black font-outfit text-white tracking-tight">
              Crop<span style={{ color: "var(--emerald-accent)" }}>Hub</span>
            </span>
          </div>
          <h1 className="text-6xl font-outfit font-black mb-6 leading-tight text-white tracking-tighter">
            Welcome<br /><span style={{ color: "var(--emerald-accent)" }}>Back.</span>
          </h1>
          <p className="text-white/40 text-lg mb-12 leading-relaxed font-medium">
            Your crops, your data, your decisions — all in one AI-powered place.
          </p>
          <div className="space-y-4">
            {highlights.map(({ icon: Icon, text }) => (
              <div key={text} className="flex items-center gap-4">
                <div className="w-8 h-8 rounded-xl bg-white/5 flex items-center justify-center shrink-0 border border-white/5 shadow-inner">
                  <Icon className="w-4 h-4" style={{ color: "var(--emerald-accent)" }} />
                </div>
                <span className="text-sm font-bold text-white/40 uppercase tracking-widest">{text}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Right form panel ── */}
      <div className="flex-1 flex items-center justify-center px-6 py-12">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }} className="w-full max-w-md">
          {/* Mobile logo */}
          <div className="lg:hidden flex items-center gap-3 mb-10">
            <Sprout className="w-8 h-8" style={{ color: "var(--emerald-accent)" }} />
            <span className="text-2xl font-outfit font-black text-white">
              Crop<span style={{ color: "var(--emerald-accent)" }}>Hub</span>
            </span>
          </div>

          <h2 className="text-4xl font-outfit font-black mb-2 text-white">Log in</h2>
          <p className="mb-10 text-white/40 text-sm font-medium">
            Enter your credentials to access your dashboard.
          </p>

          {error && (
            <div className="mb-5 px-4 py-3 rounded-xl text-sm"
              style={{ background: "rgba(255,80,80,0.08)", border: "1px solid rgba(255,80,80,0.25)", color: "#ff8080" }}>
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Email */}
            <div className="space-y-2">
              <Label htmlFor="email" className="text-xs font-bold uppercase tracking-[0.2em] text-white/20">Email Address</Label>
              <div className="relative group">
                <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-white/20 group-focus-within:text-emerald-accent transition-colors" />
                <Input id="email" type="email" placeholder="farmer@crophub.com"
                  value={email} onChange={(e) => setEmail(e.target.value)}
                  required disabled={isSubmitting}
                  className="pl-12 h-14 rounded-2xl text-sm bg-white/5 border-white/5 focus:border-emerald-accent/30 focus:ring-4 focus:ring-emerald-accent/10 text-white placeholder:text-white/10 transition-all font-medium" />
              </div>
            </div>

            {/* Password */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="password" className="text-xs font-bold uppercase tracking-[0.2em] text-white/20">Security Key</Label>
                <Link to="#" className="text-xs font-bold uppercase tracking-widest transition-colors" style={{ color: "var(--emerald-accent)" }}>Recover Access</Link>
              </div>
              <div className="relative group">
                <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-white/20 group-focus-within:text-emerald-accent transition-colors" />
                <Input id="password" type={showPassword ? "text" : "password"} placeholder="••••••••"
                  value={password} onChange={(e) => setPassword(e.target.value)}
                  required disabled={isSubmitting}
                  className="pl-12 pr-12 h-14 rounded-2xl text-sm bg-white/5 border-white/5 focus:border-emerald-accent/30 focus:ring-4 focus:ring-emerald-accent/10 text-white placeholder:text-white/10 transition-all font-medium" />
                <button type="button" onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-white/10 hover:text-emerald-accent transition-colors">
                  {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
            </div>

            {/* Remember me */}
            <div className="flex items-center gap-3">
              <Checkbox id="remember" checked={remember}
                onCheckedChange={(v) => setRemember(Boolean(v))} disabled={isSubmitting}
                className="w-5 h-5 rounded-lg bg-white/5 border-white/10 data-[state=checked]:bg-emerald-accent data-[state=checked]:border-emerald-accent" />
              <Label htmlFor="remember" className="text-xs font-bold uppercase tracking-widest text-white/30 cursor-pointer select-none">
                Maintain Session
              </Label>
            </div>

            <motion.button type="submit" disabled={isSubmitting}
              whileHover={{ scale: 1.01, y: -1 }} whileTap={{ scale: 0.99 }}
              className="btn-primary w-full h-14 rounded-2xl font-black uppercase tracking-[0.2em] flex items-center justify-center gap-4 disabled:opacity-50">
              {isSubmitting ? (
                <><span className="w-5 h-5 border-4 border-[#003919]/20 border-t-[#003919] rounded-full animate-spin" /> INITIALIZING…</>
              ) : (
                <>Log in <ArrowRight className="w-5 h-5" /></>
              )}
            </motion.button>
          </form>

          <div className="flex items-center gap-4 my-8">
            <div className="flex-1 h-px bg-white/5" />
            <span className="text-[10px] font-black uppercase tracking-[0.2em] text-white/10">External Access</span>
            <div className="flex-1 h-px bg-white/5" />
          </div>

          <button disabled className="w-full h-14 rounded-2xl flex items-center justify-center gap-4 text-xs font-bold uppercase tracking-widest bg-white/5 border border-white/5 text-white/40 opacity-50 cursor-not-allowed hover:bg-white/10 transition-all">
            <svg className="w-5 h-5" viewBox="0 0 24 24">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" />
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
            </svg>
            Continue with Google
          </button>

          <p className="text-center text-[10px] sm:text-xs font-bold uppercase tracking-[0.2em] mt-10 text-white/20">
            No secure account?{" "}
            <Link to="/signup" className="transition-colors" style={{ color: "var(--emerald-accent)" }}>Initialize Signup</Link>
          </p>
        </motion.div>
      </div>
    </div>
  );
}