import { useLocation, useNavigate } from "react-router-dom";
import { useEffect, useRef } from "react";
import { motion } from "framer-motion";
import { Sprout, Home, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";

const NotFound = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const previousPath = useRef<string | null>(null);

  useEffect(() => {
    // Capture whatever was in history before landing here
    previousPath.current = document.referrer ? new URL(document.referrer).pathname : null;
    console.error("404 Error: User attempted to access non-existent route:", location.pathname);
  }, [location.pathname]);

  function handleGoBack() {
    // If there's real browser history to go back to, use it
    if (window.history.length > 1) {
      navigate(-1);
    } else {
      navigate("/dashboard", { replace: true });
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-6">
      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="text-center max-w-md"
      >
        {/* Logo mark */}
        <div className="flex justify-center mb-8">
          <div className="w-16 h-16 rounded-2xl flex items-center justify-center" style={{ background: "rgba(0,232,122,0.12)", border: "1px solid rgba(0,232,122,0.25)" }}>
            <Sprout className="w-8 h-8" style={{ color: "var(--emerald-accent)" }} />
          </div>
        </div>

        {/* Big 404 */}
        <motion.h1
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ delay: 0.1, duration: 0.4 }}
          className="text-8xl font-bold font-outfit text-primary mb-2 leading-none"
        >
          404
        </motion.h1>

        <h2 className="text-2xl font-semibold text-foreground mb-3 font-outfit">
          Page not found
        </h2>
        <p className="text-muted-foreground mb-10 leading-relaxed">
          The route{" "}
          <code className="px-1.5 py-0.5 rounded bg-muted text-sm font-mono text-foreground">
            {location.pathname}
          </code>{" "}
          doesn't exist. You may have followed a broken link or mistyped the address.
        </p>

        {/* Actions */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
          <Button
            onClick={handleGoBack}
            variant="outline"
            className="w-full sm:w-auto h-11 px-6 rounded-xl border-border"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Go back
          </Button>

          <Button
            onClick={() => navigate("/dashboard", { replace: true })}
            className="btn-primary w-full sm:w-auto h-11 px-6 rounded-xl"
          >
            <Home className="w-4 h-4 mr-2" />
            Dashboard
          </Button>
        </div>
      </motion.div>
    </div>
  );
};

export default NotFound;