import { useState, useRef, useEffect } from "react";
import { NavLink, Link, useLocation, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  LayoutDashboard, Layers, BarChart3, Truck,
  ChevronLeft, ChevronRight, Sprout, Settings,
  LogOut, ChevronUp,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";

const navItems = [
  { title: "Dashboard", path: "/dashboard", icon: LayoutDashboard },
  { title: "Terra Layer", path: "/terra", icon: Layers },
  { title: "Fathom Layer", path: "/fathom", icon: BarChart3 },
  { title: "Logistics", path: "/logistics", icon: Truck },
];

function getInitials(name: string): string {
  return name.split(" ").filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join("");
}

function getAvatarHue(str: string): number {
  let hash = 0;
  for (let i = 0; i < str.length; i++) hash = str.charCodeAt(i) + ((hash << 5) - hash);
  return Math.abs(hash) % 360;
}

export function AppSidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  function handleLogout() { setMenuOpen(false); logout(); navigate("/login", { replace: true }); }
  function handleSettings() { setMenuOpen(false); navigate("/settings"); }

  const initials = user ? getInitials(user.name) : "?";
  const avatarHue = user ? getAvatarHue(user.name) : 153;

  return (
    <motion.aside
      animate={{ width: collapsed ? 72 : 248 }}
      transition={{ duration: 0.3, ease: "easeInOut" }}
      className="h-screen sticky top-0 flex flex-col z-50 overflow-visible shrink-0"
      style={{ background: "rgb(var(--surface-container-low))" }}
    >
      {/* ── Logo ── */}
      <Link to="/" className="flex items-center gap-3 px-4 h-16 border-b shrink-0 hover:opacity-80 transition-opacity" style={{ borderColor: "rgba(0,232,122,0.08)" }}>
        <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
          style={{ background: "rgba(0,232,122,0.12)", border: "1px solid rgba(0,232,122,0.25)" }}>
          <Sprout className="w-4 h-4" style={{ color: "#00e87a" }} />
        </div>
        <AnimatePresence>
          {!collapsed && (
            <motion.span
              initial={{ opacity: 0, width: 0 }}
              animate={{ opacity: 1, width: "auto" }}
              exit={{ opacity: 0, width: 0 }}
              className="text-lg font-bold whitespace-nowrap overflow-hidden font-outfit"
              style={{ color: "rgb(var(--on-surface))" }}
            >
              Crop<span style={{ color: "#00e87a" }}>Hub</span>
            </motion.span>
          )}
        </AnimatePresence>
      </Link>

      {/* ── Nav ── */}
      <nav className="flex-1 py-4 px-2 space-y-0.5">
        {navItems.map((item) => {
          const isActive = location.pathname === item.path;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              className="relative flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200 group"
              style={{
                background: isActive ? "rgba(0,232,122,0.1)" : "transparent",
                color: isActive ? "#00e87a" : "rgba(217,230,220,0.6)",
              }}
              onMouseEnter={(e) => {
                if (!isActive) (e.currentTarget as HTMLElement).style.background = "rgba(0,232,122,0.05)";
                if (!isActive) (e.currentTarget as HTMLElement).style.color = "rgb(217,230,220)";
              }}
              onMouseLeave={(e) => {
                if (!isActive) (e.currentTarget as HTMLElement).style.background = "transparent";
                if (!isActive) (e.currentTarget as HTMLElement).style.color = "rgba(217,230,220,0.6)";
              }}
            >
              {/* Active indicator bar */}
              {isActive && (
                <motion.div
                  layoutId="activeBar"
                  className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 rounded-full"
                  style={{ background: "#00e87a" }}
                  transition={{ type: "spring", stiffness: 400, damping: 30 }}
                />
              )}
              <item.icon className="w-4.5 h-4.5 shrink-0" />
              <AnimatePresence>
                {!collapsed && (
                  <motion.span
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="text-sm font-medium whitespace-nowrap overflow-hidden"
                  >
                    {item.title}
                  </motion.span>
                )}
              </AnimatePresence>
            </NavLink>
          );
        })}
      </nav>

      {/* ── User card ── */}
      <div className="px-2 pb-2 border-t relative" ref={menuRef} style={{ borderColor: "rgba(0,232,122,0.08)" }}>
        <AnimatePresence>
          {menuOpen && (
            <motion.div
              initial={{ opacity: 0, y: 8, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 8, scale: 0.95 }}
              transition={{ duration: 0.15 }}
              className="absolute bottom-full left-2 right-2 mb-1 rounded-xl overflow-hidden shadow-2xl z-50"
              style={{
                background: "rgb(var(--surface-container-high))",
                border: "1px solid rgba(0,232,122,0.12)",
              }}
            >
              <div className="px-4 py-3" style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
                <p className="text-xs uppercase tracking-wider font-medium" style={{ color: "rgba(186,203,186,0.5)" }}>Signed in as</p>
                <p className="text-sm font-semibold truncate mt-0.5" style={{ color: "rgb(var(--on-surface))" }}>{user?.name}</p>
                <p className="text-xs truncate" style={{ color: "rgba(186,203,186,0.6)" }}>{user?.email}</p>
              </div>
              <button onClick={handleSettings}
                className="w-full flex items-center gap-3 px-4 py-3 text-sm transition-colors hover:bg-white/5"
                style={{ color: "rgba(217,230,220,0.8)" }}>
                <Settings className="w-4 h-4 shrink-0" />
                <span>Settings</span>
              </button>
              <button onClick={handleLogout}
                className="w-full flex items-center gap-3 px-4 py-3 text-sm text-red-400 hover:bg-red-500/10 transition-colors"
                style={{ borderTop: "1px solid rgba(255,255,255,0.05)" }}>
                <LogOut className="w-4 h-4 shrink-0" />
                <span>Log out</span>
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        <button
          onClick={() => setMenuOpen((o) => !o)}
          className="w-full mt-2 flex items-center gap-3 px-2 py-2.5 rounded-xl transition-colors"
          style={{ background: menuOpen ? "rgba(0,232,122,0.06)" : "transparent" }}
          onMouseEnter={(e) => { if (!menuOpen) (e.currentTarget as HTMLElement).style.background = "rgba(0,232,122,0.05)"; }}
          onMouseLeave={(e) => { if (!menuOpen) (e.currentTarget as HTMLElement).style.background = "transparent"; }}
        >
          <div
            className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold shrink-0 text-white ring-2"
            style={{ background: `hsl(${avatarHue}, 50%, 30%)`, ringColor: "rgba(0,232,122,0.25)" }}
          >
            {initials}
          </div>
          <AnimatePresence>
            {!collapsed && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="flex-1 min-w-0 text-left">
                <p className="text-sm font-semibold truncate leading-tight" style={{ color: "rgb(var(--on-surface))" }}>
                  {user?.name ?? "Account"}
                </p>
                <p className="text-xs truncate leading-tight" style={{ color: "rgba(186,203,186,0.5)" }}>
                  {user?.email ?? ""}
                </p>
              </motion.div>
            )}
          </AnimatePresence>
          <AnimatePresence>
            {!collapsed && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="shrink-0">
                <ChevronUp className={`w-4 h-4 transition-transform`}
                  style={{ color: "rgba(186,203,186,0.5)", transform: menuOpen ? "rotate(180deg)" : "rotate(0deg)" }} />
              </motion.div>
            )}
          </AnimatePresence>
        </button>
      </div>

      {/* ── Collapse toggle ── */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="flex items-center justify-center h-9 transition-colors"
        style={{ borderTop: "1px solid rgba(0,232,122,0.08)", color: "rgba(186,203,186,0.4)" }}
        onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.color = "#00e87a"; }}
        onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.color = "rgba(186,203,186,0.4)"; }}
      >
        {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
      </button>
    </motion.aside>
  );
}