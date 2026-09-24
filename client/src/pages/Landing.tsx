import { useRef, useState, useEffect, useCallback } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  motion, AnimatePresence, useScroll, useTransform, useInView, useSpring, useMotionValue,
} from "framer-motion";
import {
  Sprout, Layers, BarChart3, Truck, ArrowRight, Leaf, TrendingUp, Shield, Zap,
  ChevronDown, Settings, LogOut, LayoutDashboard, Scan, Globe, Star, CheckCircle2,
  Activity, Cpu, Twitter, Github, Linkedin, Play
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";

/* ─── Scroll-triggered section wrapper ─── */
function ScrollSection({ children, className = "", delay = 0 }: { children: React.ReactNode; className?: string; delay?: number; }) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-80px" });
  return (
    <motion.section ref={ref} initial={{ opacity: 0, y: 50 }} animate={isInView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.7, ease: "easeOut", delay }} className={className}>
      {children}
    </motion.section>
  );
}

/* ─── 3D tilt card on mouse hover ─── */
function TiltCard({ children, className = "" }: { children: React.ReactNode; className?: string; }) {
  const ref = useRef<HTMLDivElement>(null);
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const rotateX = useSpring(useTransform(y, [-0.5, 0.5], [8, -8]), { stiffness: 300, damping: 30 });
  const rotateY = useSpring(useTransform(x, [-0.5, 0.5], [-8, 8]), { stiffness: 300, damping: 30 });

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    x.set((e.clientX - rect.left) / rect.width - 0.5);
    y.set((e.clientY - rect.top) / rect.height - 0.5);
  }, [x, y]);
  const handleMouseLeave = useCallback(() => { x.set(0); y.set(0); }, [x, y]);

  return (
    <motion.div ref={ref} style={{ rotateX, rotateY, transformStyle: "preserve-3d" }}
      onMouseMove={handleMouseMove} onMouseLeave={handleMouseLeave} className={className}>
      {children}
    </motion.div>
  );
}

/* ─── Animated particle canvas ─── */
function ParticleField() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const resize = () => { canvas.width = window.innerWidth; canvas.height = window.innerHeight; };
    resize();
    window.addEventListener("resize", resize);

    const particles = Array.from({ length: 80 }).map(() => ({
      x: Math.random() * canvas.width, y: Math.random() * canvas.height,
      vx: (Math.random() - 0.5) * 0.3, vy: (Math.random() - 0.5) * 0.3,
      radius: Math.random() * 1.5 + 0.3, alpha: Math.random(), fadeDir: Math.random() > 0.5 ? 1 : -1,
    }));
    let animId: number;
    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      particles.forEach((p) => {
        p.x += p.vx; p.y += p.vy; p.alpha += p.fadeDir * 0.003;
        if (p.alpha >= 1 || p.alpha <= 0) p.fadeDir *= -1;
        if (p.x < 0) p.x = canvas.width; if (p.x > canvas.width) p.x = 0;
        if (p.y < 0) p.y = canvas.height; if (p.y > canvas.height) p.y = 0;
        ctx.beginPath(); ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(0, 232, 122, ${p.alpha * 0.6})`; ctx.fill();
      });
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x, dy = particles[i].y - particles[j].y, dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 100) {
            ctx.beginPath(); ctx.moveTo(particles[i].x, particles[i].y); ctx.lineTo(particles[j].x, particles[j].y);
            ctx.strokeStyle = `rgba(0, 232, 122, ${(1 - dist / 100) * 0.08})`; ctx.lineWidth = 0.5; ctx.stroke();
          }
        }
      }
      animId = requestAnimationFrame(draw);
    };
    draw();
    return () => { cancelAnimationFrame(animId); window.removeEventListener("resize", resize); };
  }, []);
  return <canvas ref={canvasRef} className="absolute inset-0 pointer-events-none" style={{ zIndex: 0 }} />;
}

/* ─── Animated counter ─── */
function AnimatedCounter({ target, suffix = "", prefix = "" }: { target: number; suffix?: string; prefix?: string; }) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true });
  const [count, setCount] = useState(0);
  useEffect(() => {
    if (!isInView) return;
    let start = 0; const increment = target / (1800 / 16);
    const timer = setInterval(() => {
      start += increment;
      if (start >= target) { setCount(target); clearInterval(timer); } else { setCount(Math.floor(start)); }
    }, 16);
    return () => clearInterval(timer);
  }, [isInView, target]);
  return <span ref={ref}>{prefix}{count}{suffix}</span>;
}

const stats = [
  { value: 40, suffix: "%", label: "Yield Increase", icon: TrendingUp },
  { prefix: "₹", value: 2, suffix: ".4L", label: "Avg. Savings", icon: Globe },
  { value: 12, suffix: "K+", label: "Active Farmers", icon: Leaf },
  { value: 98, suffix: "%", label: "Accuracy Rate", icon: Activity },
];

const features = [
  {
    icon: Layers, title: "Terra Layer", description: "AI-powered soil diagnostics. Upload a photo and get instant NPK, pH, and health analysis for optimized growth.",
    accent: "text-emerald-accent", bg: "bg-emerald-accent/10", border: "border-emerald-accent/20", to: "/terra", badge: "Soil AI",
  },
  {
    icon: BarChart3, title: "Fathom Layer", description: "Predictive crop allocation. Enter your budget and land size to get an optimised planting plan backed by data.",
    accent: "text-harvest-gold", bg: "bg-harvest-gold/10", border: "border-harvest-gold/20", to: "/fathom", badge: "Crop AI",
  },
  {
    icon: Truck, title: "Logistics Hub", description: "Market arbitrage engine. Compare real-time pricing across nearby markets to maximise profit on every harvest.",
    accent: "text-loam-warm", bg: "bg-loam-warm/10", border: "border-loam-warm/20", to: "/logistics", badge: "Market AI",
  },
];

/* ═══════════════════════════════════════════════════════════════════════ */
export default function Landing() {
  const heroRef = useRef(null);
  const { scrollYProgress } = useScroll({ target: heroRef, offset: ["start start", "end start"] });
  const heroY = useTransform(scrollYProgress, [0, 1], [0, 160]);
  const heroOpacity = useTransform(scrollYProgress, [0, 0.75], [1, 0]);

  const { isAuthenticated, user, logout } = useAuth();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    function handleClick(e: MouseEvent) { if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false); }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const initials = user ? user.name.split(" ").filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join("") : "";
  const avatarHue = user ? Math.abs([...user.name].reduce((h, c) => c.charCodeAt(0) + ((h << 5) - h), 0)) % 360 : 153;

  return (
    <div className="landing-page min-h-screen overflow-x-hidden">

      {/* ── NAVBAR (file 1) ─────────────────────────────────────────── */}
      <motion.nav className="fixed top-0 w-full z-50 transition-all duration-500"
        animate={scrolled
          ? { backgroundColor: "rgba(var(--surface-rgb), 0.9)", backdropFilter: "blur(20px)", borderBottom: "1px solid rgba(0,232,122,0.1)" }
          : { backgroundColor: "transparent", backdropFilter: "blur(0px)", borderBottom: "1px solid transparent" }}>
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2.5 group">
            <div className="w-8 h-8 rounded-lg bg-emerald-accent/10 border border-emerald-accent/30 flex items-center justify-center group-hover:bg-emerald-accent/20 transition-colors">
              <Sprout className="w-4.5 h-4.5 text-emerald-accent" />
            </div>
            <span className="text-lg font-bold text-white font-outfit tracking-tight">
              Crop<span className="text-emerald-accent">Hub</span>
            </span>
          </Link>
          <div className="hidden md:flex items-center gap-8 text-sm font-medium">
            {["#features", "#how-it-works", "#impact"].map((href, i) => (
              <a key={href} href={href} className="text-surface-variant hover:text-white transition-colors relative group">
                {["Features", "How It Works", "Impact"][i]}
                <span className="absolute -bottom-0.5 left-0 w-0 h-px bg-emerald-accent group-hover:w-full transition-all duration-300" />
              </a>
            ))}
          </div>
          <div className="flex items-center gap-3">
            {isAuthenticated && user ? (
              <div className="relative" ref={menuRef}>
                <button onClick={() => setMenuOpen((o) => !o)} className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-surface-container transition-colors">
                  <div className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold text-white shrink-0 ring-2 ring-emerald-accent/30" style={{ background: `hsl(${avatarHue}, 60%, 30%)` }}>{initials}</div>
                  <ChevronDown className={`w-3.5 h-3.5 text-surface-variant transition-transform ${menuOpen ? "rotate-180" : ""}`} />
                </button>
                <AnimatePresence>
                  {menuOpen && (
                    <motion.div initial={{ opacity: 0, y: 8, scale: 0.96 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 8, scale: 0.96 }}
                      className="absolute right-0 mt-2 w-56 rounded-xl border border-emerald-accent/10 bg-surface-container-high/95 backdrop-blur-xl shadow-2xl overflow-hidden z-50">
                      <div className="px-4 py-3 border-b border-white/5">
                        <p className="text-xs text-surface-variant uppercase tracking-wider font-medium">Signed in as</p>
                        <p className="text-sm font-semibold text-white truncate mt-0.5">{user.name}</p>
                      </div>
                      <button onClick={() => navigate("/dashboard")} className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-white/80 hover:text-white hover:bg-surface-container-highest transition-colors">
                        <LayoutDashboard className="w-4 h-4 text-surface-variant" /> Dashboard
                      </button>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            ) : (
              <>
                <Link to="/login" className="text-sm font-medium text-surface-variant hover:text-white transition-colors px-4 py-2">Log in</Link>
                <Link to="/signup" className="btn-primary text-sm font-semibold px-5 py-2 rounded-lg">Get Started</Link>
              </>
            )}
          </div>
        </div>
      </motion.nav>

      {/* ── HERO (file 1) ─────────────────────────────────────────── */}
      <section ref={heroRef} className="relative min-h-screen pt-24 pb-16 overflow-hidden bg-surface flex items-center">
        <div className="absolute inset-0 pointer-events-none overflow-hidden">
          <motion.div animate={{ scale: [1, 1.15, 1], opacity: [0.3, 0.5, 0.3] }} transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
            className="absolute -top-32 -left-32 w-[600px] h-[600px] rounded-full"
            style={{ background: "radial-gradient(circle, rgba(0,232,122,0.15) 0%, transparent 70%)", filter: "blur(60px)" }} />
          <motion.div animate={{ scale: [1, 1.2, 1], opacity: [0.2, 0.4, 0.2] }} transition={{ duration: 10, repeat: Infinity, ease: "easeInOut", delay: 3 }}
            className="absolute top-1/4 -right-48 w-[500px] h-[500px] rounded-full"
            style={{ background: "radial-gradient(circle, rgba(245,166,35,0.1) 0%, transparent 70%)", filter: "blur(60px)" }} />
        </div>
        <ParticleField />
        <div className="absolute inset-0 pointer-events-none opacity-[0.03]"
          style={{ backgroundImage: "linear-gradient(#00e87a 1px, transparent 1px), linear-gradient(90deg, #00e87a 1px, transparent 1px)", backgroundSize: "60px 60px" }} />

        <div className="max-w-7xl mx-auto px-6 grid grid-cols-1 lg:grid-cols-12 gap-12 items-center relative z-10 w-full">
          {/* Left */}
          <motion.div style={{ y: heroY, opacity: heroOpacity }} className="lg:col-span-7 pt-10">
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}
              className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-semibold mb-8"
              style={{ background: "rgba(0, 232, 122, 0.08)", border: "1px solid rgba(0, 232, 122, 0.25)", color: "#00E87A" }}>
              <Zap className="w-3.5 h-3.5" /> AI-Powered Agriculture Platform
            </motion.div>
            <motion.h1 initial={{ opacity: 0, y: 40 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, delay: 0.2 }}
              className="text-5xl md:text-7xl font-outfit font-black text-white leading-[1.05] mb-6 tracking-tight">
              Farm Smarter.<br /><span className="hero-gradient-text">Harvest More.</span>
            </motion.h1>
            <motion.p initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, delay: 0.4 }}
              className="text-lg text-surface-variant max-w-xl mb-10 leading-relaxed">
              CropHub combines soil diagnostics, predictive crop planning, and market intelligence into one AI decision engine — built for the modern farmer.
            </motion.p>
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.6 }}
              className="flex flex-col sm:flex-row items-center gap-4">
              <Link to="/signup">
                <motion.button whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.97 }} className="btn-primary flex items-center gap-2 text-base px-8 py-3.5 rounded-xl font-bold">
                  Start Free <ArrowRight className="w-4 h-4" />
                </motion.button>
              </Link>
              <div className="flex items-center gap-4 text-xs text-surface-variant ml-4">
                <span className="flex items-center gap-1.5"><CheckCircle2 className="w-3.5 h-3.5 text-emerald-accent" /> No credit card</span>
                <span className="flex items-center gap-1.5"><Shield className="w-3.5 h-3.5 text-emerald-accent" /> SOC 2 compliant</span>
              </div>
            </motion.div>
          </motion.div>

          {/* Right mockup */}
          <motion.div initial={{ opacity: 0, scale: 0.9, rotateY: 15 }} animate={{ opacity: 1, scale: 1, rotateY: 0 }} transition={{ duration: 1, delay: 0.3 }}
            className="hidden lg:block lg:col-span-5 relative perspective-[1000px]">
            <TiltCard>
              <div className="w-full aspect-[4/5] rounded-3xl overflow-hidden glass-card border border-emerald-accent/20 p-6 flex flex-col shadow-2xl shadow-emerald-accent/10">
                <div className="flex items-center justify-between mb-8">
                  <div className="w-10 h-10 rounded-xl bg-emerald-accent/20 flex items-center justify-center"><Leaf className="w-5 h-5 text-emerald-accent" /></div>
                  <span className="text-xs font-mono font-bold text-emerald-accent px-3 py-1 bg-emerald-accent/10 rounded-full border border-emerald-accent/20">Live Sync</span>
                </div>
                <div className="space-y-4 flex-1">
                  <div className="h-24 rounded-2xl bg-surface-container/50 border border-white/5 p-4">
                    <p className="text-xs text-surface-variant mb-2">Soil Health Score</p>
                    <div className="flex items-end gap-3"><span className="text-3xl font-black text-white font-outfit">92</span><span className="text-sm text-emerald-accent font-semibold mb-1">+4%</span></div>
                  </div>
                  <div className="h-24 rounded-2xl bg-surface-container/50 border border-white/5 p-4">
                    <p className="text-xs text-surface-variant mb-2">Optimal Crop</p>
                    <div className="flex justify-between items-center"><span className="text-xl font-bold text-harvest-gold">Soybean</span><span className="text-xs text-surface-variant">80% Match</span></div>
                    <div className="w-full h-1.5 bg-white/10 rounded-full mt-3"><div className="h-full bg-harvest-gold rounded-full w-[80%]" /></div>
                  </div>
                </div>
              </div>
            </TiltCard>
          </motion.div>
        </div>
      </section>

      {/* ── MARQUEE (file 2) ──────────────────────────────────────── */}
      <div className="py-6 border-y border-white/5 bg-surface-container-low flex overflow-hidden relative">
        <div className="absolute left-0 top-0 bottom-0 w-32 bg-gradient-to-r from-surface-container-low to-transparent z-10" />
        <div className="absolute right-0 top-0 bottom-0 w-32 bg-gradient-to-l from-surface-container-low to-transparent z-10" />
        <motion.div animate={{ x: ["0%", "-50%"] }} transition={{ duration: 20, ease: "linear", repeat: Infinity }}
          className="flex whitespace-nowrap items-center min-w-max">
          {[...Array(2)].map((_, i) => (
            <div key={i} className="flex gap-16 px-8 items-center">
              {["Trusted by top agritech partners", "Over 12,000 acres monitored daily", "₹2.4L average annual savings per farm", "98% diagnostic accuracy via CNN"].map(t => (
                <span key={t} className="text-sm font-semibold uppercase tracking-widest text-surface-variant/70 flex items-center gap-3">
                  <Star className="w-3 h-3 text-emerald-accent" /> {t}
                </span>
              ))}
            </div>
          ))}
        </motion.div>
      </div>

      {/* ── FEATURES (file 2) ──────────────────────────────────────── */}
      <section id="features" className="py-32 px-6">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-24">
            <h2 className="text-4xl md:text-6xl font-black text-white mb-6">Built for <span className="text-emerald-accent">Modern</span> Agriculture</h2>
            <p className="text-white/40 text-lg max-w-2xl mx-auto">Harness the power of AI across three distinct layers designed to maximize your efficiency.</p>
          </div>
          <div className="grid md:grid-cols-3 gap-8">
            {features.map((feature, i) => (
              <ScrollSection key={feature.title} delay={i * 0.1}>
                <TiltCard className="h-full">
                  <div className="glass-card h-full p-10 rounded-[2.5rem] flex flex-col group border border-white/5 hover:border-emerald-accent/30">
                    <div className="w-14 h-14 rounded-2xl bg-emerald-accent/10 flex items-center justify-center border border-emerald-accent/20 mb-8 group-hover:scale-110 transition-transform">
                      <feature.icon className="w-7 h-7 text-emerald-accent" />
                    </div>
                    <h3 className="text-2xl font-bold text-white mb-4">{feature.title}</h3>
                    <p className="text-white/50 leading-relaxed mb-8 flex-1">{feature.description}</p>
                    <Link to={feature.to} className="flex items-center gap-2 text-emerald-accent font-bold text-sm">
                      Learn more <ArrowRight className="w-4 h-4" />
                    </Link>
                  </div>
                </TiltCard>
              </ScrollSection>
            ))}
          </div>
        </div>
      </section>

      {/* ── HOW IT WORKS (file 2) ──────────────────────────────────── */}
      <section id="how-it-works" className="py-32 px-6 relative">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-24">
            <h2 className="text-4xl md:text-6xl font-black text-white mb-6">How <span className="text-emerald-accent">It Works</span></h2>
            <p className="text-white/40 text-lg">Three simple steps to transition your farm into the AI era.</p>
          </div>
          <div className="grid md:grid-cols-3 gap-8">
            {[
              { num: "01", title: "Scan Soil", desc: "Upload a photo or enter data. AI models analyze composition instantly.", icon: Scan },
              { num: "02", title: "Plan Target", desc: "Generate optimal crop mix mapping based on your budget & land size.", icon: Cpu },
              { num: "03", title: "Sell High", desc: "Track markets to find the most profitable buyer accounting for transport.", icon: Truck }
            ].map((step, i) => (
              <ScrollSection key={step.num} delay={i * 0.1}>
                <div className="p-10 rounded-[2.5rem] border border-white/5 relative overflow-hidden group"
                  style={{ background: "rgb(var(--surface-container-lowest))" }}>
                  <span className="absolute -right-4 -top-8 text-[12rem] font-black text-white/5 leading-none select-none">{step.num}</span>
                  <div className="w-16 h-16 rounded-2xl bg-emerald-accent/10 flex items-center justify-center mb-8 border border-emerald-accent/20 group-hover:scale-110 transition-transform">
                    <step.icon className="w-8 h-8 text-emerald-accent" />
                  </div>
                  <h3 className="text-2xl font-bold text-white mb-4 relative z-10">{step.title}</h3>
                  <p className="text-white/40 leading-relaxed relative z-10">{step.desc}</p>
                </div>
              </ScrollSection>
            ))}
          </div>
        </div>
      </section>

      {/* ── TESTIMONIALS (file 2) ──────────────────────────────────── */}
      <section id="impact" className="py-32 px-6">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-24">
            <h2 className="text-4xl md:text-6xl font-black text-white">Farmers Love <span className="text-emerald-accent">CropHub</span></h2>
          </div>
          <div className="grid md:grid-cols-3 gap-8">
            {[
              { name: "Ravi Kumar", role: "Wheat Farmer", text: "Saved lakhs in fertilizer costs. The AI accuracy is unbelievable.", border: "hover:border-emerald-accent/30" },
              { name: "Priya Sharma", role: "Rice Farmer", text: "Found a buyer paying 20% more via the Logistics Hub.", border: "hover:border-harvest-gold/30" },
              { name: "Mohan Das", role: "Vegetable Farmer", text: "Fathom Layer pushed my yield up by 40% in one season.", border: "hover:border-emerald-accent/30" }
            ].map((t, i) => (
              <ScrollSection key={t.name} delay={i * 0.1}>
                <div className={`glass-card p-10 rounded-[2.5rem] border border-white/5 transition-all ${t.border}`}>
                  <div className="flex items-center gap-1 mb-6">
                    {[1, 2, 3, 4, 5].map((s) => (
                      <Star key={s} className="w-4 h-4 fill-harvest-gold text-harvest-gold" />
                    ))}
                  </div>
                  <p className="text-xl text-white/70 italic mb-8">"{t.text}"</p>
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-full bg-white/10" />
                    <div>
                      <p className="font-bold text-white">{t.name}</p>
                      <p className="text-white/40 text-sm">{t.role}</p>
                    </div>
                  </div>
                </div>
              </ScrollSection>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA (file 2) ───────────────────────────────────────────── */}
      <section className="py-32 px-6">
        <div className="max-w-7xl mx-auto">
          <div className="p-12 md:p-20 rounded-[3rem] relative overflow-hidden shadow-[0_0_100px_rgba(0,232,122,0.15)]">
            <div className="absolute inset-0 bg-gradient-to-br from-[#00e87a] to-[#00c860]" />
            <div className="absolute inset-0 opacity-[0.1]" style={{
              backgroundImage: "linear-gradient(rgba(0,57,25,1) 1px, transparent 1px), linear-gradient(90deg, rgba(0,57,25,1) 1px, transparent 1px)",
              backgroundSize: "24px 24px"
            }} />
            <div className="relative z-10 text-center max-w-3xl mx-auto">
              <h2 className="text-4xl md:text-6xl font-black mb-8 text-[#003919] leading-tight">
                Ready to maximize your harvest?
              </h2>
              <div className="flex flex-col sm:flex-row items-center justify-center gap-6">
                <Link to="/signup" className="w-full sm:w-auto h-16 px-12 rounded-2xl bg-[#003919] text-white text-xl font-bold hover:bg-[#002b13] transition-all flex items-center justify-center gap-3 shadow-2xl">
                  Get Started Now <ArrowRight className="w-6 h-6" />
                </Link>
                <button className="w-full sm:w-auto h-16 px-12 rounded-2xl bg-white/20 backdrop-blur-md text-white text-xl font-bold hover:bg-white/30 transition-all flex items-center justify-center gap-3 border border-white/20">
                  Contact Sales <Play className="w-5 h-5" fill="currentColor" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── FOOTER (file 2) ────────────────────────────────────────── */}
      <footer className="py-20 px-6 border-t border-white/5">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-12 text-center md:text-left">
            <div>
              <div className="flex items-center gap-2 mb-6">
                <div className="w-8 h-8 rounded-lg bg-emerald-accent/10 flex items-center justify-center border border-emerald-accent/20">
                  <Sprout className="w-4 h-4 text-emerald-accent" />
                </div>
                <span className="text-xl font-bold text-white tracking-tight">CropHub</span>
              </div>
              <p className="text-white/40 text-sm leading-relaxed">
                Building the future of sustainable, data-driven agriculture.
              </p>
            </div>
            {["Platform", "Product", "Social"].map((title, i) => (
              <div key={title}>
                <h4 className="text-white font-bold mb-6">{title}</h4>
                <ul className="space-y-4 text-white/40 text-sm">
                  {i === 2 ? (
                    <>
                      <li className="hover:text-emerald-accent cursor-pointer">Twitter</li>
                      <li className="hover:text-emerald-accent cursor-pointer">LinkedIn</li>
                      <li className="hover:text-emerald-accent cursor-pointer">Instagram</li>
                    </>
                  ) : (
                    <>
                      <li className="hover:text-emerald-accent cursor-pointer">Features</li>
                      <li className="hover:text-emerald-accent cursor-pointer">Solutions</li>
                      <li className="hover:text-emerald-accent cursor-pointer">Pricing</li>
                    </>
                  )}
                </ul>
              </div>
            ))}
          </div>
          <div className="mt-20 pt-8 border-t border-white/5 flex flex-col md:flex-row items-center justify-between gap-6">
            <p className="text-white/20 text-xs tracking-widest uppercase">© 2026 CropHub. All rights reserved.</p>
            <div className="flex gap-8 text-white/20 text-xs tracking-widest uppercase">
              <span className="hover:text-white cursor-pointer transition-colors">Privacy Policy</span>
              <span className="hover:text-white cursor-pointer transition-colors">Terms of Service</span>
            </div>
          </div>
        </div>
      </footer>

    </div>
  );
}