import { AnimatePresence, motion } from "framer-motion";
import { Route, Routes, useLocation } from "react-router-dom";
import { Landing } from "./pages/Landing";
import { Dashboard } from "./pages/Dashboard";
import { Operations } from "./pages/Operations";
import { Layout } from "./Layout";

const page = {
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -12 },
  transition: { duration: 0.45, ease: [0.2, 0.7, 0.2, 1] as const },
};

function Animated({ children }: { children: React.ReactNode }) {
  return <motion.div {...page}>{children}</motion.div>;
}

export default function App() {
  const loc = useLocation();
  return (
    <AnimatePresence mode="wait">
      <Routes location={loc} key={loc.pathname}>
        <Route path="/" element={<Animated><Landing /></Animated>} />
        <Route element={<Layout />}>
          <Route path="/dashboard" element={<Animated><Dashboard /></Animated>} />
          <Route path="/operations" element={<Animated><Operations /></Animated>} />
        </Route>
      </Routes>
    </AnimatePresence>
  );
}
