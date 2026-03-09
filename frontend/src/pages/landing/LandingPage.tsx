/**
 * Premium marketing landing page for Imperecta.
 * Public route: /ai.market.intelligence.agent
 * Standalone layout — no dashboard shell.
 */

import { useEffect } from "react";
import { Link } from "react-router-dom";
import {
  BarChart3,
  Bell,
  Brain,
  Gauge,
  LineChart,
  Sparkles,
  Target,
  TrendingUp,
  Zap,
} from "lucide-react";

const LANDING_GRADIENT = "linear-gradient(135deg, #050810 0%, #0a0e1a 25%, #0d1525 50%, #0a1628 100%)";
const LANDING_ACCENT = "#38bdf8";
const LANDING_ACCENT_DIM = "#0ea5e9";

function LandingHeader() {
  return (
    <header className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-6 py-4 backdrop-blur-md">
      <div className="flex items-center gap-2">
        <img src="/images/logo-dark.png" alt="Imperecta" className="h-8 w-auto" />
        <span className="font-display text-lg font-bold tracking-tight text-white">
          Imperecta
        </span>
      </div>
      <div className="flex items-center gap-4">
        <Link
          to="/login"
          className="text-sm font-medium text-white/80 transition-colors hover:text-white"
        >
          Sign in
        </Link>
        <Link
          to="/register"
          className="rounded-lg bg-white/10 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-white/20"
        >
          Request Demo
        </Link>
      </div>
    </header>
  );
}

function HeroSection() {
  const previewCards = [
    { label: "Competitor coverage", value: "12", trend: "marketplaces" },
    { label: "Market pressure index", value: "98.2", trend: "+2.1% WoW" },
    { label: "Strategic alerts", value: "3", trend: "today" },
    { label: "7-day forecast", value: "+5%", trend: "category" },
  ];

  return (
    <section className="relative min-h-[90vh] overflow-hidden px-6 pt-36 pb-24">
      <div className="absolute inset-0" style={{ background: LANDING_GRADIENT }} />
      <div
        className="absolute -top-40 -right-40 h-96 w-96 rounded-full opacity-20 blur-[100px]"
        style={{ background: LANDING_ACCENT }}
      />
      <div
        className="absolute top-1/2 -left-20 h-64 w-64 rounded-full opacity-10 blur-[80px]"
        style={{ background: "#0ea5e9" }}
      />
      <div className="absolute inset-0 opacity-30">
        <svg className="h-full w-full" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <pattern id="grid" width="60" height="60" patternUnits="userSpaceOnUse">
              <path d="M 60 0 L 0 0 0 60" fill="none" stroke="rgba(255,255,255,0.03)" strokeWidth="0.5" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid)" />
        </svg>
      </div>

      <div className="relative mx-auto max-w-7xl">
        <div className="grid gap-16 lg:grid-cols-2 lg:gap-20">
          <div className="flex flex-col justify-center">
            <p className="mb-5 text-xs font-medium uppercase tracking-[0.2em] text-white/50">
              AI Market Intelligence Platform
            </p>
            <h1 className="font-display text-4xl font-bold leading-[1.1] tracking-tight text-white sm:text-5xl lg:text-6xl">
              See market shifts{" "}
              <span className="bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">
                before they hit revenue
              </span>
            </h1>
            <p className="mt-8 max-w-lg text-base leading-relaxed text-white/75">
              Competitor intelligence, pricing signals, forecasting, and strategic alerts in one platform.
              Built for e-commerce brands, retailers, and marketplace operators.
            </p>
            <div className="mt-12 flex flex-wrap gap-4">
              <Link
                to="/register"
                className="inline-flex items-center gap-2 rounded-xl px-8 py-4 text-base font-semibold text-white transition-all hover:opacity-95"
                style={{
                  background: `linear-gradient(135deg, ${LANDING_ACCENT_DIM}, ${LANDING_ACCENT})`,
                  boxShadow: "0 0 32px rgba(14, 165, 233, 0.35)",
                }}
              >
                Request Demo
              </Link>
              <Link
                to="/login"
                className="inline-flex items-center gap-2 rounded-xl border border-white/20 bg-white/5 px-8 py-4 text-base font-semibold text-white backdrop-blur-sm transition-colors hover:border-white/30 hover:bg-white/10"
              >
                Explore Platform
              </Link>
            </div>
          </div>
          <div className="relative hidden lg:block">
            <div className="absolute inset-0 rounded-3xl border border-white/10 bg-white/[0.03] backdrop-blur-xl" />
            <div className="relative grid grid-cols-2 gap-4 p-6">
              {previewCards.map((card, i) => (
                <div
                  key={i}
                  className="rounded-2xl border border-white/10 bg-white/5 p-5 backdrop-blur-sm"
                >
                  <p className="text-xs font-medium uppercase tracking-wider text-white/50">
                    {card.label}
                  </p>
                  <p className="mt-2 font-display text-2xl font-bold text-white">{card.value}</p>
                  <p className="mt-1 text-sm text-cyan-400/90">{card.trend}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function TrustStrip() {
  const items = [
    "Competitor monitoring",
    "Pricing intelligence",
    "Benchmark analytics",
    "Forecasting",
    "Strategic alerting",
  ];

  return (
    <section className="border-y border-white/10 bg-black/40 py-10">
      <div className="mx-auto max-w-7xl px-6">
        <div className="flex flex-wrap items-center justify-center gap-x-12 gap-y-4 md:gap-x-16">
          {items.map((item, i) => (
            <div key={i} className="flex items-center gap-2.5">
              <div
                className="h-1 w-1 rounded-full"
                style={{ background: LANDING_ACCENT }}
              />
              <span className="text-sm font-medium text-white/75">{item}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function WhatImperectaDoes() {
  const cards = [
    {
      icon: Target,
      title: "Competitor monitoring",
      desc: "Track competitor moves across marketplaces and digital commerce channels. Assortment, pricing, and market behavior in one view.",
    },
    {
      icon: Zap,
      title: "Pricing intelligence",
      desc: "Detect pricing shifts, discount pressure, and positioning changes. Know where you stand and where you drift.",
    },
    {
      icon: BarChart3,
      title: "Benchmark analytics",
      desc: "Compare your position against market players. Pricing, visibility, competitiveness over time.",
    },
    {
      icon: Brain,
      title: "AI insights",
      desc: "Turn fragmented market data into decision-ready intelligence. Patterns, anomalies, and risks surfaced automatically.",
    },
    {
      icon: LineChart,
      title: "Forecasting",
      desc: "Anticipate market changes before they affect revenue. Predictive signals for pricing and demand movements.",
    },
    {
      icon: Gauge,
      title: "Strategic alerting",
      desc: "Detect unusual competitor moves and critical market changes early. React quickly without manual monitoring.",
    },
  ];

  return (
    <section className="relative overflow-hidden px-6 py-28" style={{ background: LANDING_GRADIENT }}>
      <div className="mx-auto max-w-7xl">
        <p className="mb-3 text-xs font-medium uppercase tracking-[0.2em] text-white/50">
          Platform capabilities
        </p>
        <h2 className="font-display text-3xl font-bold tracking-tight text-white sm:text-4xl">
          What Imperecta does
        </h2>
        <p className="mt-4 max-w-xl text-base text-white/65">
          Fragmented market data becomes structured intelligence. Manual monitoring becomes continuous strategic visibility.
        </p>
        <div className="mt-20 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {cards.map((card, i) => (
            <div
              key={i}
              className="group rounded-2xl border border-white/10 bg-white/[0.03] p-6 backdrop-blur-xl transition-colors hover:border-white/15 hover:bg-white/5"
            >
              <card.icon className="mb-4 size-8 text-cyan-400/90" />
              <h3 className="font-display text-lg font-semibold text-white">{card.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-white/65">{card.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function FeatureSection() {
  const features = [
    { icon: BarChart3, title: "Market monitoring", desc: "Multi-source, multi-marketplace coverage. Continuous visibility." },
    { icon: Sparkles, title: "AI analyst", desc: "Ask questions in natural language. Get strategic answers from market data." },
    { icon: TrendingUp, title: "Pricing intelligence", desc: "Assortment, positioning, competitive gaps. Live market signals." },
    { icon: Bell, title: "Strategic alerting", desc: "Unusual moves and critical changes surfaced early. Configurable thresholds." },
    { icon: LineChart, title: "Forecasting", desc: "Predictive analytics. Scenario modeling. Plan ahead." },
    { icon: Gauge, title: "Executive dashboards", desc: "Market position and decision context at a glance." },
  ];

  return (
    <section className="relative overflow-hidden px-6 py-28">
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-cyan-950/5 to-transparent" />
      <div className="relative mx-auto max-w-7xl">
        <p className="mb-3 text-xs font-medium uppercase tracking-[0.2em] text-white/50">
          Product
        </p>
        <h2 className="font-display text-3xl font-bold tracking-tight text-white sm:text-4xl">
          Built for pricing, category, and market intelligence teams
        </h2>
        <div className="mt-20 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((f, i) => (
            <div
              key={i}
              className="flex gap-5 rounded-2xl border border-white/10 bg-white/[0.03] p-6 backdrop-blur-xl"
            >
              <div className="flex size-12 shrink-0 items-center justify-center rounded-xl bg-cyan-500/15">
                <f.icon className="size-6 text-cyan-400/90" />
              </div>
              <div>
                <h3 className="font-display font-semibold text-white">{f.title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-white/65">{f.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function WhyTeamsChoose() {
  const items = [
    {
      pain: "Reacting too late to competitor moves",
      outcome: "Market changes surfaced in real time. Act before competitors.",
    },
    {
      pain: "Fragmented spreadsheets and manual checks",
      outcome: "One platform. Unified competitor and market data.",
    },
    {
      pain: "Raw dashboards without decision support",
      outcome: "AI insights, forecasts, and recommendations. Actionable intelligence.",
    },
  ];

  return (
    <section className="relative overflow-hidden px-6 py-28" style={{ background: LANDING_GRADIENT }}>
      <div className="mx-auto max-w-7xl">
        <p className="mb-3 text-xs font-medium uppercase tracking-[0.2em] text-white/50">
          Business impact
        </p>
        <h2 className="font-display text-3xl font-bold tracking-tight text-white sm:text-4xl">
          From reactive to strategic
        </h2>
        <p className="mt-4 max-w-xl text-base text-white/65">
          Faster commercial decisions. Earlier detection. Less manual monitoring. More confident pricing and category actions.
        </p>
        <div className="mt-20 grid gap-6 md:grid-cols-3">
          {items.map((item, i) => (
            <div
              key={i}
              className="rounded-2xl border border-white/10 bg-white/[0.03] p-8 backdrop-blur-xl"
            >
              <p className="text-xs font-medium uppercase tracking-wider text-cyan-400/90">
                Without Imperecta
              </p>
              <h3 className="mt-2 font-display text-xl font-semibold text-white">{item.pain}</h3>
              <p className="mt-5 text-sm font-medium text-white/75">With Imperecta</p>
              <p className="mt-1.5 text-sm leading-relaxed text-white/65">{item.outcome}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function PlatformPreview() {
  const priceRows = [
    { product: "SKU-2847", marketplace: "Marketplace A", price: "₽1,240", change: "+2.1%" },
    { product: "SKU-9102", marketplace: "Marketplace B", price: "₽890", change: "−1.2%" },
    { product: "SKU-5531", marketplace: "Marketplace C", price: "₽1,100", change: "stable" },
  ];

  const alerts = [
    { msg: "Competitor price shift detected — 15% drop", type: "price" },
    { msg: "Promo detected on 2 products", type: "promo" },
    { msg: "Stock change — 3 competitors", type: "stock" },
  ];

  return (
    <section className="relative overflow-hidden px-6 py-28">
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-blue-950/5 to-transparent" />
      <div className="relative mx-auto max-w-7xl">
        <p className="mb-3 text-xs font-medium uppercase tracking-[0.2em] text-white/50">
          Platform preview
        </p>
        <h2 className="font-display text-3xl font-bold tracking-tight text-white sm:text-4xl">
          Intelligence in action
        </h2>
        <p className="mt-4 max-w-xl text-base text-white/65">
          Competitor price movement, market signals, forecasts, and strategic alerts — unified in one view.
        </p>
        <div className="mt-20 grid gap-6 lg:grid-cols-2">
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-6 backdrop-blur-xl">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-white/60">Competitor price movement</span>
              <span className="rounded-full bg-cyan-500/15 px-2.5 py-0.5 text-xs font-medium text-cyan-400">
                Live
              </span>
            </div>
            <div className="mt-5 space-y-2">
              {priceRows.map((row, i) => (
                <div
                  key={i}
                  className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-lg border border-white/5 bg-white/5 px-4 py-3 text-sm"
                >
                  <span className="text-white/90">{row.product}</span>
                  <span className="text-white/55">{row.marketplace}</span>
                  <span className="ml-auto font-mono text-cyan-400/90">{row.price}</span>
                  <span className="font-mono text-white/75">{row.change}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-6 backdrop-blur-xl">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-white/60">Strategic alerts</span>
            </div>
            <div className="mt-5 space-y-2">
              {alerts.map((a, i) => (
                <div
                  key={i}
                  className="flex items-center gap-3 rounded-lg border border-amber-500/15 bg-amber-500/5 px-4 py-3"
                >
                  <div className="h-2 w-2 shrink-0 rounded-full bg-amber-400/90" />
                  <span className="text-sm text-white/90">{a.msg}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function TestimonialsSection() {
  const testimonials = [
    {
      quote: "Faster decision speed. We see market shifts in real time instead of after the fact.",
      role: "Pricing Director",
    },
    {
      quote: "The AI analyst answers questions we used to spend hours researching. Clearer market visibility.",
      role: "Category Manager",
    },
    {
      quote: "One platform for competitor and market data. Stronger pricing response, better leadership insight.",
      role: "Commercial Director",
    },
  ];

  return (
    <section className="relative overflow-hidden px-6 py-28" style={{ background: LANDING_GRADIENT }}>
      <div className="mx-auto max-w-7xl">
        <p className="mb-3 text-xs font-medium uppercase tracking-[0.2em] text-white/50">
          Trusted by teams
        </p>
        <h2 className="font-display text-3xl font-bold tracking-tight text-white sm:text-4xl">
          What pricing and commercial teams say
        </h2>
        <div className="mt-20 grid gap-6 md:grid-cols-3">
          {testimonials.map((t, i) => (
            <div
              key={i}
              className="rounded-2xl border border-white/10 bg-white/[0.03] p-6 backdrop-blur-xl"
            >
              <p className="text-[15px] leading-relaxed text-white/85">&ldquo;{t.quote}&rdquo;</p>
              <p className="mt-5 text-xs font-medium text-white/50">{t.role}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function CTASection() {
  return (
    <section className="relative overflow-hidden px-6 py-32">
      <div
        className="absolute inset-0"
        style={{
          background: `linear-gradient(135deg, rgba(6, 78, 159, 0.25) 0%, rgba(14, 165, 233, 0.15) 50%, transparent 100%)`,
        }}
      />
      <div className="relative mx-auto max-w-3xl text-center">
        <h2 className="font-display text-3xl font-bold tracking-tight text-white sm:text-4xl lg:text-5xl">
          See Imperecta in action
        </h2>
        <p className="mt-6 text-base leading-relaxed text-white/70">
          Request a demo. See how Imperecta helps pricing and market teams make faster commercial decisions.
        </p>
        <div className="mt-12 flex flex-wrap justify-center gap-4">
          <Link
            to="/register"
            className="inline-flex items-center gap-2 rounded-xl px-8 py-4 text-base font-semibold text-white transition-opacity hover:opacity-95"
            style={{
              background: `linear-gradient(135deg, ${LANDING_ACCENT_DIM}, ${LANDING_ACCENT})`,
              boxShadow: "0 0 32px rgba(14, 165, 233, 0.35)",
            }}
          >
            Request Demo
          </Link>
          <Link
            to="/login"
            className="inline-flex items-center gap-2 rounded-xl border border-white/20 bg-white/5 px-8 py-4 text-base font-semibold text-white backdrop-blur-sm transition-colors hover:border-white/30 hover:bg-white/10"
          >
            Explore Platform
          </Link>
        </div>
      </div>
    </section>
  );
}

function LandingFooter() {
  return (
    <footer className="border-t border-white/10 px-6 py-16">
      <div className="mx-auto max-w-7xl">
        <div className="flex flex-col gap-10 md:flex-row md:items-start md:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <img src="/images/logo-dark.png" alt="Imperecta" className="h-6 w-auto" />
              <span className="font-display text-lg font-bold text-white">Imperecta</span>
            </div>
            <p className="mt-3 max-w-xs text-sm text-white/55">
              AI Market Intelligence for e-commerce teams. Faster visibility, sharper competitive context, more confident commercial decisions.
            </p>
          </div>
          <div className="flex flex-wrap gap-8">
            <div>
              <p className="text-xs font-medium uppercase tracking-wider text-white/60">Product</p>
              <ul className="mt-2 space-y-1">
                <li><Link to="/ai.market.intelligence.agent" className="text-sm text-white/80 hover:text-white">Features</Link></li>
                <li><Link to="/ai.market.intelligence.agent#platform" className="text-sm text-white/80 hover:text-white">Platform</Link></li>
              </ul>
            </div>
            <div>
              <p className="text-xs font-medium uppercase tracking-wider text-white/60">Company</p>
              <ul className="mt-2 space-y-1">
                <li><a href="#" className="text-sm text-white/80 hover:text-white">Security</a></li>
                <li><a href="#" className="text-sm text-white/80 hover:text-white">Privacy</a></li>
                <li><a href="#" className="text-sm text-white/80 hover:text-white">Terms</a></li>
                <li><a href="#" className="text-sm text-white/80 hover:text-white">Contact</a></li>
              </ul>
            </div>
          </div>
        </div>
        <div className="mt-12 border-t border-white/10 pt-8 text-center text-sm text-white/50">
          © {new Date().getFullYear()} Imperecta. All rights reserved.
        </div>
      </div>
    </footer>
  );
}

const LANDING_TITLE = "Imperecta — AI Market Intelligence for E-commerce";
const LANDING_DESCRIPTION =
  "AI Market Intelligence platform for e-commerce and retail. Competitor monitoring, pricing intelligence, benchmark analytics, forecasting, and strategic alerting.";

export function LandingPage() {
  useEffect(() => {
    const prevTitle = document.title;
    const meta = document.querySelector('meta[name="description"]');
    const prevDesc = meta?.getAttribute("content") ?? "";
    document.title = LANDING_TITLE;
    if (meta) meta.setAttribute("content", LANDING_DESCRIPTION);
    return () => {
      document.title = prevTitle;
      if (meta) meta.setAttribute("content", prevDesc);
    };
  }, []);

  return (
    <div
      className="min-h-screen text-white"
      style={{ background: LANDING_GRADIENT }}
    >
      <LandingHeader />
      <main>
        <HeroSection />
        <TrustStrip />
        <WhatImperectaDoes />
        <FeatureSection />
        <WhyTeamsChoose />
        <section id="platform">
          <PlatformPreview />
        </section>
        <TestimonialsSection />
        <CTASection />
        <LandingFooter />
      </main>
    </div>
  );
}
