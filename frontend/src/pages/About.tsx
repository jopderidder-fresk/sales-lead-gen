import { cn } from "@/lib/utils";
import {
  BarChart3,
  Building2,
  Compass,
  ExternalLink,
  LayoutDashboard,
  Radio,
  Settings,
  Target,
  CheckCircle2,
  ArrowRight,
} from "lucide-react";
import { NavLink } from "react-router-dom";

const steps = [
  {
    number: "01",
    icon: Target,
    title: "Define your ICP",
    description:
      "Start by building one or more Ideal Customer Profiles. Tell fresk which industries, company sizes, tech stacks, and growth signals matter to you.",
  },
  {
    number: "02",
    icon: Compass,
    title: "Run discovery",
    description:
      "Trigger a discovery job manually or set a recurring schedule. fresk scours the web for companies that match your ICP and pulls them into your pipeline.",
  },
  {
    number: "03",
    icon: Building2,
    title: "Enrich & review",
    description:
      "Discovered companies are automatically enriched with contacts, technology stack details, and company metadata. Review everything in the Companies view.",
  },
  {
    number: "04",
    icon: Radio,
    title: "Monitor signals",
    description:
      "Real-time sales triggers keep you ahead of the curve — hiring surges, funding rounds, leadership changes, product launches, and more.",
  },
  {
    number: "05",
    icon: ExternalLink,
    title: "Push to ClickUp",
    description:
      "When a company is ready, send it straight to your ClickUp workspace as a task. Your existing sales workflow takes it from there.",
  },
];

const features = [
  {
    icon: LayoutDashboard,
    title: "Dashboard",
    to: "/",
    description:
      "Your command center. See total leads, active signals, pipeline stages, and conversion trends at a glance — all updated in real time.",
    highlights: ["KPI cards", "Pipeline funnel", "Recent signals", "Conversion metrics"],
  },
  {
    icon: Building2,
    title: "Companies",
    to: "/companies",
    description:
      "Browse, filter, and manage every company in your pipeline. Sort by ICP match score, status, or discovery date.",
    highlights: ["ICP scoring", "Status pipeline", "Contact details", "Tech stack"],
  },
  {
    icon: Radio,
    title: "Signals",
    to: "/signals",
    description:
      "A live feed of sales triggers. Act on each signal instantly: notify now, add to digest, trigger enrichment, or dismiss.",
    highlights: ["Hiring surges", "Funding rounds", "Leadership changes", "Product launches"],
  },
  {
    icon: Target,
    title: "ICP",
    to: "/icp",
    description:
      "Define exactly who your ideal customer is. Multiple active profiles let you pursue different segments at the same time.",
    highlights: ["Industry filters", "Size ranges", "Tech requirements", "Growth criteria"],
  },
  {
    icon: Compass,
    title: "Discovery",
    to: "/discovery",
    description:
      "Trigger discovery jobs on demand or set a recurring schedule. Full job history shows duration, results, and status at a glance.",
    highlights: ["On-demand runs", "Daily / weekly schedules", "Job history", "Result counts"],
  },
  {
    icon: BarChart3,
    title: "Analytics",
    to: "/analytics",
    description:
      "Track pipeline health over time. Leads added, signals by type, conversion funnel, enrichment rates, and API cost tracking.",
    highlights: ["Leads over time", "Signal breakdown", "Conversion funnel", "API cost tracking"],
  },
  {
    icon: Settings,
    title: "Settings",
    to: "/settings",
    description:
      "Connect your tools and configure limits. Admin users manage integrations for the whole team from one place.",
    highlights: ["ClickUp integration", "Slack notifications", "Usage limits", "Role-based access"],
  },
];

export default function About() {
  return (
    <div className="max-w-5xl mx-auto space-y-20 pb-16 animate-enter">
      {/* ── Hero ─────────────────────────────────────────────── */}
      <section className="pt-4 space-y-5">
        <div
          className="inline-flex items-center gap-2 rounded-full border border-amber/40 bg-amber/10 px-3.5 py-1 text-xs font-medium text-amber-foreground animate-fade-in"
          style={{ animationDelay: "0ms" }}
        >
          <span className="h-1.5 w-1.5 rounded-full bg-amber inline-block" />
          fresk.digital
        </div>

        <h1
          className="text-5xl leading-tight text-foreground animate-enter-up"
          style={{ animationDelay: "60ms" }}
        >
          Your automated
          <br />
          <span className="text-amber">sales intelligence</span> engine
        </h1>

        <p
          className="text-lg text-muted-foreground max-w-2xl leading-relaxed animate-enter-up"
          style={{ animationDelay: "120ms" }}
        >
          fresk.digital discovers companies that match your ideal customer
          profile, enriches them with real contact data and tech signals, then
          drops qualified leads straight into your ClickUp workflow — on
          autopilot.
        </p>
      </section>

      {/* ── How it works ─────────────────────────────────────── */}
      <section className="space-y-8 animate-enter-up" style={{ animationDelay: "180ms" }}>
        <div className="space-y-1">
          <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
            The workflow
          </p>
          <h2 className="text-3xl text-foreground">How it works</h2>
        </div>

        <div className="relative">
          {/* Connector line — desktop only */}
          <div className="hidden lg:block absolute left-8 top-10 bottom-10 w-px bg-gradient-to-b from-amber/60 via-border to-transparent" />

          <div className="space-y-4">
            {steps.map(({ number, icon: Icon, title, description }, i) => (
              <div
                key={number}
                className="relative flex gap-5 rounded-xl border border-border bg-card p-5 transition-all duration-200 hover:border-amber/40 hover:shadow-sm animate-enter-up"
                style={{ animationDelay: `${220 + i * 60}ms` }}
              >
                {/* Step number + icon */}
                <div className="relative z-10 flex flex-col items-center gap-2 shrink-0">
                  <div className={cn(
                    "flex h-10 w-10 items-center justify-center rounded-full border",
                    i === 0
                      ? "border-amber/50 bg-amber/15 text-amber-foreground"
                      : "border-border bg-secondary text-muted-foreground"
                  )}>
                    <Icon className="h-[18px] w-[18px]" />
                  </div>
                </div>

                {/* Content */}
                <div className="flex-1 space-y-1">
                  <div className="flex items-baseline gap-3">
                    <span className="font-mono text-[10px] text-muted-foreground/60 select-none">
                      {number}
                    </span>
                    <h3 className="text-base font-semibold text-foreground" style={{ fontFamily: "DM Serif Display, Georgia, serif" }}>
                      {title}
                    </h3>
                  </div>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    {description}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Features ─────────────────────────────────────────── */}
      <section className="space-y-8 animate-enter-up" style={{ animationDelay: "300ms" }}>
        <div className="space-y-1">
          <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
            The platform
          </p>
          <h2 className="text-3xl text-foreground">Every page, explained</h2>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {features.map(({ icon: Icon, title, to, description, highlights }, i) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                cn(
                  "group relative flex flex-col gap-4 rounded-xl border p-5 transition-all duration-200 hover:shadow-sm animate-enter-up",
                  isActive
                    ? "border-amber/50 bg-amber/5 shadow-sm"
                    : "border-border bg-card hover:border-amber/30",
                )
              }
              style={{ animationDelay: `${340 + i * 50}ms` }}
            >
              {({ isActive }) => (
                <>
                  {/* Icon */}
                  <div className={cn(
                    "flex h-9 w-9 items-center justify-center rounded-lg border transition-colors duration-200",
                    isActive
                      ? "border-amber/40 bg-amber/15 text-amber-foreground"
                      : "border-border bg-secondary text-muted-foreground group-hover:border-amber/30 group-hover:bg-amber/10 group-hover:text-amber-foreground"
                  )}>
                    <Icon className="h-4.5 w-4.5" />
                  </div>

                  {/* Title + description */}
                  <div className="space-y-1.5 flex-1">
                    <h3 className="text-sm font-semibold text-foreground" style={{ fontFamily: "DM Serif Display, Georgia, serif" }}>
                      {title}
                    </h3>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      {description}
                    </p>
                  </div>

                  {/* Highlights */}
                  <ul className="space-y-1">
                    {highlights.map((h) => (
                      <li
                        key={h}
                        className="flex items-center gap-1.5 text-xs text-muted-foreground"
                      >
                        <CheckCircle2 className={cn(
                          "h-3 w-3 shrink-0",
                          isActive ? "text-amber" : "text-muted-foreground/40 group-hover:text-amber/60"
                        )} />
                        {h}
                      </li>
                    ))}
                  </ul>

                  {isActive && (
                    <div className="absolute top-3 right-3">
                      <span className="inline-flex items-center gap-1 rounded-full bg-amber/20 px-2 py-0.5 text-[10px] font-medium text-amber-foreground">
                        Current
                      </span>
                    </div>
                  )}
                </>
              )}
            </NavLink>
          ))}
        </div>
      </section>

      {/* ── Company statuses ─────────────────────────────────── */}
      <section className="space-y-8 animate-enter-up" style={{ animationDelay: "380ms" }}>
        <div className="space-y-1">
          <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
            Pipeline stages
          </p>
          <h2 className="text-3xl text-foreground">Company statuses</h2>
          <p className="text-sm text-muted-foreground leading-relaxed max-w-2xl">
            Every company in fresk moves through a pipeline. Each status tells you exactly where a company sits and what happened to it last.
          </p>
        </div>

        <div className="space-y-3">
          {[
            {
              status: "Discovered",
              color: "bg-blue-50 text-blue-700 ring-blue-200",
              dot: "bg-blue-500",
              description:
                "The company was found by a discovery job and added to your pipeline. No enrichment has run yet — you have a name and domain, but little else.",
            },
            {
              status: "Enriched",
              color: "bg-purple-50 text-purple-700 ring-purple-200",
              dot: "bg-purple-500",
              description:
                "Enrichment has run successfully. The company now has contacts, tech stack details, company metadata, and an ICP match score so you can evaluate fit.",
            },
            {
              status: "Monitoring",
              color: "bg-cyan-50 text-cyan-700 ring-cyan-200",
              dot: "bg-cyan-500",
              description:
                "The company is being actively watched for sales signals — hiring surges, funding rounds, leadership changes, product launches, and more. Signals appear in your feed the moment they're detected.",
            },
            {
              status: "Qualified",
              color: "bg-green-50 text-green-700 ring-green-200",
              dot: "bg-green-500",
              description:
                "You've reviewed the company and marked it as a strong fit. It's ready to be actioned — either pushed to ClickUp or handed off to your sales team.",
            },
            {
              status: "Pushed",
              color: "bg-emerald-50 text-emerald-700 ring-emerald-200",
              dot: "bg-emerald-500",
              description:
                "The company has been sent to ClickUp as a task. Your existing sales workflow takes over from here. fresk continues monitoring for new signals in the background.",
            },
            {
              status: "Archived",
              color: "bg-gray-50 text-gray-600 ring-gray-200",
              dot: "bg-gray-400",
              description:
                "The company has been dismissed from your active pipeline — not a fit right now, duplicate, or out of scope. Archived companies are hidden from the default view but remain in the database.",
            },
          ].map(({ status, color, dot, description }, i) => (
            <div
              key={status}
              className="flex gap-4 rounded-xl border border-border bg-card p-5 transition-all duration-200 hover:border-amber/30 animate-enter-up"
              style={{ animationDelay: `${420 + i * 40}ms` }}
            >
              <div className="shrink-0 pt-0.5">
                <span className={cn("h-2 w-2 rounded-full inline-block mt-1.5", dot)} />
              </div>
              <div className="flex-1 space-y-1.5">
                <span
                  className={cn(
                    "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
                    color,
                  )}
                >
                  {status}
                </span>
                <p className="text-sm text-muted-foreground leading-relaxed">{description}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Flow arrow */}
        <div className="flex items-center gap-2 text-xs text-muted-foreground/60 pl-1">
          <ArrowRight className="h-3 w-3" />
          <span>Typical flow: Discovered → Enriched → Monitoring → Qualified → Pushed</span>
        </div>
      </section>

      {/* ── APIs & Services ────────────────────────────────── */}
      <section className="space-y-8 animate-enter-up" style={{ animationDelay: "460ms" }}>
        <div className="space-y-1">
          <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
            Under the hood
          </p>
          <h2 className="text-3xl text-foreground">APIs &amp; Services</h2>
          <p className="text-sm text-muted-foreground leading-relaxed max-w-2xl">
            fresk orchestrates multiple third-party APIs to discover, enrich,
            and monitor companies. Here is every external service the platform
            talks to and what it does.
          </p>
        </div>

        {/* Data & Enrichment */}
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-foreground" style={{ fontFamily: "DM Serif Display, Georgia, serif" }}>
            Data &amp; Enrichment
          </h3>
          {[
            {
              name: "Firecrawl",
              detail:
                "Web search, scraping, and multi-page crawling. Powers discovery jobs (finding companies that match your ICP) and signal monitoring (scraping company pages for news and changes).",
            },
            {
              name: "Hunter.io",
              detail:
                "Email finding and verification. First provider in the contact enrichment waterfall — searches for contacts by company domain and verifies email deliverability.",
            },
            {
              name: "ScrapIn",
              detail:
                "GDPR-compliant professional data enrichment. Second provider in the waterfall — finds contacts using public professional profiles without requiring a LinkedIn login.",
            },
            {
              name: "Bedrijfsdata.nl",
              detail:
                "Dutch company search and enrichment using KvK (Chamber of Commerce) registry data. Provides company metadata, employee counts, revenue, SBI industry codes, and tech stack detection.",
            },
          ].map(({ name, detail }, i) => (
            <div
              key={name}
              className="flex gap-4 rounded-xl border border-border bg-card p-5 transition-all duration-200 hover:border-amber/30 animate-enter-up"
              style={{ animationDelay: `${500 + i * 40}ms` }}
            >
              <div className="shrink-0 pt-0.5">
                <span className="h-2 w-2 rounded-full bg-foreground/30 inline-block mt-1.5" />
              </div>
              <div className="flex-1 space-y-1">
                <p className="text-sm font-semibold text-foreground">{name}</p>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  {detail}
                </p>
              </div>
            </div>
          ))}
        </div>

        {/* AI & Language Models */}
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-foreground" style={{ fontFamily: "DM Serif Display, Georgia, serif" }}>
            AI &amp; Language Models
          </h3>
          {[
            {
              name: "Anthropic Claude",
              detail:
                "Primary LLM provider. Uses Haiku for fast tasks (signal classification, structured data extraction) and Sonnet for complex tasks (relevance scoring, company profiling). Powers all AI-driven analysis in the pipeline.",
            },
            {
              name: "OpenRouter",
              detail:
                "Alternative LLM provider. Routes requests to a selection of open and proprietary models via a unified API. Acts as a fallback when Anthropic is not configured.",
            },
            {
              name: "Google Gemini",
              detail:
                "Alternative LLM provider using Google's Gemini models (Flash for speed, Pro for quality). Available as a drop-in replacement via the LLM provider setting.",
            },
            {
              name: "Google Vertex AI",
              detail:
                "Enterprise-grade LLM provider for Google Cloud environments. Uses service-account authentication and runs in europe-west1 by default. Suitable for teams with existing GCP infrastructure.",
            },
          ].map(({ name, detail }, i) => (
            <div
              key={name}
              className="flex gap-4 rounded-xl border border-border bg-card p-5 transition-all duration-200 hover:border-amber/30 animate-enter-up"
              style={{ animationDelay: `${700 + i * 40}ms` }}
            >
              <div className="shrink-0 pt-0.5">
                <span className="h-2 w-2 rounded-full bg-foreground/30 inline-block mt-1.5" />
              </div>
              <div className="flex-1 space-y-1">
                <p className="text-sm font-semibold text-foreground">{name}</p>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  {detail}
                </p>
              </div>
            </div>
          ))}
        </div>

        {/* Workflow & Notifications */}
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-foreground" style={{ fontFamily: "DM Serif Display, Georgia, serif" }}>
            Workflow &amp; Notifications
          </h3>
          {[
            {
              name: "ClickUp",
              detail:
                "Task management integration. When a company reaches the Qualified stage, fresk creates a ClickUp task with all enriched data, contacts, and signal history. Ongoing signals are added as comments on the task automatically.",
            },
            {
              name: "Slack",
              detail:
                "Real-time notifications via incoming webhooks. Sends immediate alerts for high-scoring signals, daily digest summaries of all pipeline activity, and weekly reports with top leads and conversion stats.",
            },
          ].map(({ name, detail }, i) => (
            <div
              key={name}
              className="flex gap-4 rounded-xl border border-border bg-card p-5 transition-all duration-200 hover:border-amber/30 animate-enter-up"
              style={{ animationDelay: `${860 + i * 40}ms` }}
            >
              <div className="shrink-0 pt-0.5">
                <span className="h-2 w-2 rounded-full bg-foreground/30 inline-block mt-1.5" />
              </div>
              <div className="flex-1 space-y-1">
                <p className="text-sm font-semibold text-foreground">{name}</p>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  {detail}
                </p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── Footer note ──────────────────────────────────────── */}
      <p
        className="text-center text-xs text-muted-foreground/60 pb-4 animate-fade-in"
        style={{ animationDelay: "500ms" }}
      >
        Configure integrations in{" "}
        <NavLink to="/settings" className="underline underline-offset-2 hover:text-foreground transition-colors">
          Settings
        </NavLink>
        {" "}· Manage profiles in{" "}
        <NavLink to="/icp" className="underline underline-offset-2 hover:text-foreground transition-colors">
          ICP
        </NavLink>
      </p>
    </div>
  );
}
