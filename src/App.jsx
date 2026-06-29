import { useEffect, useState } from "react";
import html2canvas from "html2canvas";

const API_BASE = import.meta.env.VITE_API_BASE || "";

const reportTypes = [
  { key: "location", icon: "▦", label: "Location Wise" },
  { key: "source", icon: "◈", label: "Source Wise" },
  { key: "model", icon: "◇", label: "Model Wise" },
  { key: "target", icon: "◎", label: "Target Achievement" },
  { key: "incentive", icon: "₹", label: "Incentive" },
];

function logoSrc(brand) {
  return `/assets/${brand.toLowerCase()}.png`;
}

async function api(path, body, token) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { "X-Session-Token": token } : {}),
    },
    body: JSON.stringify(body || {}),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Request failed");
  return data;
}

function Login({ onLogin }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      onLogin(await api("/api/login", { email, password }));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-page">
      <div className="login-shell">
        <h1 className="login-brand-title">Singhania Motors Dashboard</h1>
        <form className="login-box" onSubmit={submit}>
          <h1>Welcome Back</h1>
          <p className="login-subtitle">Fill out the information below in order to access your account.</p>
          {error ? <div className="error">{error}</div> : null}
          <div className="field">
            <label>User Email</label>
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="username"
              placeholder="Enter your email id here......"
              required
            />
          </div>
          <div className="field password-wrap">
            <label>Password</label>
            <input
              type={showPassword ? "text" : "password"}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
              placeholder="Enter your Password....."
              required
            />
            <button
              type="button"
              className="password-toggle"
              onClick={() => setShowPassword(!showPassword)}
              title={showPassword ? "Hide password" : "Show password"}
            >
              {showPassword ? "◉" : "◌"}
            </button>
          </div>
          <button className="primary-btn" disabled={loading}>
            {loading ? "Signing in..." : "Sign In"}
          </button>
        </form>
      </div>
    </div>
  );
}

function Header({ user, brand, onBack, onLogout }) {
  return (
    <>
      <div className="topbar" />
      <header>
        <h1>{brand ? `${brand.toUpperCase()} GROUP SUMMARY` : "BRAND SELECTION"}</h1>
        <div className="userbar">
          <span className="muted">{user.name}</span>
          {brand ? (
            <button className="secondary-btn" onClick={onBack}>
              Brands
            </button>
          ) : null}
          <button className="secondary-btn" onClick={onLogout}>
            Logout
          </button>
        </div>
      </header>
    </>
  );
}

function BrandSelection({ user, onSelect }) {
  return (
    <main>
      <div className="brand-grid">
        {user.brands.map((brand) => (
          <button key={brand} className="brand-card" onClick={() => onSelect(brand)}>
            <div className={`brand-logo ${brand.toLowerCase()}`}>
              <img src={logoSrc(brand)} alt={`${brand} logo`} />
            </div>
            <strong>{brand}</strong>
          </button>
        ))}
      </div>
    </main>
  );
}

function ReportTabs({ reportType, onChange }) {
  return (
    <nav className="report-tabs" aria-label="Dashboard type">
      {reportTypes.map((item) => (
        <button
          key={item.key}
          className={reportType === item.key ? "active" : ""}
          onClick={() => onChange(item.key)}
        >
          <span>{item.icon}</span>
          <span>{item.label}</span>
        </button>
      ))}
    </nav>
  );
}

function MetricCards({ cards }) {
  return (
    <section className="metrics">
      {cards.map((card) => (
        <div className="metric-card" key={card.label}>
          <span>{card.label}</span>
          <strong>{card.value}</strong>
        </div>
      ))}
    </section>
  );
}

function MultiSelect({ label, options, value, onChange, placeholder }) {
  const selected = Array.isArray(value) ? value : value ? [value] : [];
  const selectedSet = new Set(selected);
  const display = selected.length ? `${selected.length} selected` : placeholder;
  const toggle = (item) => {
    onChange(selectedSet.has(item) ? selected.filter((value) => value !== item) : [...selected, item]);
  };

  return (
    <div className="field multi-field">
      <label>{label}</label>
      <details className="multi-select">
        <summary>{display}</summary>
        <div className="multi-menu">
          <button type="button" className="multi-clear" onClick={() => onChange([])}>
            Clear
          </button>
          {options.map((item) => (
            <label key={item} className="multi-option">
              <input type="checkbox" checked={selectedSet.has(item)} onChange={() => toggle(item)} />
              <span>{item}</span>
            </label>
          ))}
        </div>
      </details>
    </div>
  );
}

function Filters({ report, filters, onChange, onApply, onReset, loading }) {
  const options = report.filterOptions || { locations: [], sources: [], models: [] };
  const usesMonthRange = report.reportType === "target" || report.reportType === "incentive";
  const set = (key, value) => onChange({ ...filters, [key]: value });

  return (
    <section className="filters-panel">
      <div className="filters-title">Filters</div>
      <div className="filters-grid">
        <MultiSelect label="Location" options={options.locations} value={filters.location} onChange={(value) => set("location", value)} placeholder="All Locations" />
        <MultiSelect label="Source" options={options.sources} value={filters.source} onChange={(value) => set("source", value)} placeholder="All Sources" />
        <MultiSelect label="Model" options={options.models} value={filters.model} onChange={(value) => set("model", value)} placeholder="All Models" />
        {usesMonthRange ? (
          <>
            <div className="field">
              <label>From Month</label>
              <input type="month" value={filters.monthFrom || ""} onChange={(event) => set("monthFrom", event.target.value)} />
            </div>
            <div className="field">
              <label>To Month</label>
              <input type="month" value={filters.monthTo || ""} onChange={(event) => set("monthTo", event.target.value)} />
            </div>
          </>
        ) : (
          <>
            <div className="field">
              <label>From Date</label>
              <input type="date" value={filters.dateFrom || ""} onChange={(event) => set("dateFrom", event.target.value)} />
            </div>
            <div className="field">
              <label>To Date</label>
              <input type="date" value={filters.dateTo || ""} onChange={(event) => set("dateTo", event.target.value)} />
            </div>
          </>
        )}
        <div className="filter-actions">
          <button className="primary-btn" onClick={onApply} disabled={loading}>
            {loading ? "Applying..." : "Apply"}
          </button>
          <button className="secondary-btn" onClick={onReset} disabled={loading}>
            Reset
          </button>
        </div>
      </div>
    </section>
  );
}

function downloadCsv(table) {
  const rows = [table.headers, ...table.rows];
  const csv = rows
    .map((row) =>
      row
        .map((value) => {
          const text = String(value).replaceAll('"', '""');
          return /[",\n]/.test(text) ? `"${text}"` : text;
        })
        .join(","),
    )
    .join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${table.title.replaceAll(" ", "_")}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

function safeFileName(value) {
  return String(value || "report").replace(/[^a-z0-9]+/gi, "_").replace(/^_+|_+$/g, "").toLowerCase() || "report";
}

function WhatsAppIcon() {
  return (
    <svg className="whatsapp-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M20.5 11.8a8.4 8.4 0 0 1-12.4 7.4L4 20.5l1.3-4a8.4 8.4 0 1 1 15.2-4.7Z" />
      <path d="M8.7 8.5c.2-.5.4-.5.7-.5h.5c.2 0 .4.1.5.4l.7 1.6c.1.3 0 .5-.1.6l-.4.5c-.1.2-.2.3-.1.5.4.8 1.1 1.5 2.1 2 .2.1.4.1.5-.1l.6-.7c.2-.2.4-.2.6-.1l1.6.8c.3.1.4.3.4.5 0 .4-.2 1.1-.8 1.5-.5.4-1.3.5-2.4.1-2.1-.7-3.8-2.2-4.8-4.1-.6-1.1-.6-1.8-.4-2.3l.3-.7Z" />
    </svg>
  );
}

function DownloadIcon() {
  return (
    <svg className="download-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M12 4v11" />
      <path d="m7 10 5 5 5-5" />
      <path d="M5 20h14" />
    </svg>
  );
}

async function sharePanelOnWhatsApp(table, event) {
  const panel = event.currentTarget.closest(".panel");
  if (!panel) return;
  panel.classList.add("capturing");
  try {
    const canvas = await html2canvas(panel, {
      backgroundColor: "#ffffff",
      scale: 2,
      useCORS: true,
    });
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
    if (!blob) throw new Error("Screenshot could not be created");
    const file = new File([blob], `${safeFileName(table.title)}.png`, { type: "image/png" });
    let copied = false;
    if (navigator.clipboard && window.ClipboardItem) {
      try {
        await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
        copied = true;
      } catch {
        copied = false;
      }
    }
    if (!copied) {
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = file.name;
      link.click();
      URL.revokeObjectURL(url);
    }
    const text = copied
      ? `${table.title} screenshot copied. Paste it in this WhatsApp chat.`
      : `${table.title} screenshot downloaded. Attach the downloaded PNG in this WhatsApp chat.`;
    const encodedText = encodeURIComponent(text);
    const isMobile = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
    if (isMobile) {
      window.location.href = `whatsapp://send?text=${encodedText}`;
    } else {
      window.open(`https://web.whatsapp.com/send?text=${encodedText}`, "_blank");
    }
  } catch (error) {
    alert(error.message || "Unable to share screenshot");
  } finally {
    panel.classList.remove("capturing");
  }
}

function DataTable({ table }) {
  const headerRows = table.headerRows || [table.headers];
  const renderHeaderCell = (cell, index) => {
    if (typeof cell === "object") {
      return (
        <th key={index} colSpan={cell.colSpan || 1} rowSpan={cell.rowSpan || 1}>
          {cell.label}
        </th>
      );
    }
    return <th key={`${cell}-${index}`}>{cell}</th>;
  };

  return (
    <section className={`panel ${table.wide ? "wide" : ""}`}>
      <div className="panel-title">
        <h2>{table.title}</h2>
        <div className="actions">
          <button
            className="icon-btn"
            title="Share on WhatsApp"
            onClick={(event) => sharePanelOnWhatsApp(table, event)}
          >
            <WhatsAppIcon />
          </button>
          <button className="icon-btn" title="Download CSV" onClick={() => downloadCsv(table)}>
            <DownloadIcon />
          </button>
        </div>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            {headerRows.map((row, rowIndex) => (
              <tr key={rowIndex}>{row.map(renderHeaderCell)}</tr>
            ))}
          </thead>
          <tbody>
            {table.rows.map((row, index) => (
              <tr key={index}>
                {row.map((cell, cellIndex) => (
                  <td key={cellIndex}>{cell}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Report({ report, reportType, onReportTypeChange, filters, onFilterChange, onApplyFilters, onResetFilters, loading }) {
  return (
    <div className="report-shell">
      <main className="report-content">
        <ReportTabs reportType={reportType} onChange={onReportTypeChange} />
        <button className="filter-btn">
          {report.brand} • {report.groupLabel} Wise
        </button>
        <Filters
          report={report}
          filters={filters}
          onChange={onFilterChange}
          onApply={onApplyFilters}
          onReset={onResetFilters}
          loading={loading}
        />
        <MetricCards cards={report.cards} />
        <section className="grid">
          {report.tables.map((table) => (
            <DataTable table={table} key={table.title} />
          ))}
        </section>
        <button className="to-top" title="Back to top" onClick={() => scrollTo({ top: 0, behavior: "smooth" })}>
          ↑
        </button>
      </main>
    </div>
  );
}

export default function App() {
  const savedState = (() => {
    try {
      return JSON.parse(localStorage.getItem("singhaniaDashboardState") || "{}");
    } catch {
      return {};
    }
  })();
  const [token, setToken] = useState(savedState.token || "");
  const [user, setUser] = useState(savedState.user || null);
  const [brand, setBrand] = useState(savedState.brand || "");
  const [reportType, setReportType] = useState(savedState.reportType || "location");
  const [report, setReport] = useState(null);
  const [filters, setFilters] = useState(savedState.filters || {});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  function onLogin(result) {
    setToken(result.token);
    setUser(result.user);
  }

  useEffect(() => {
    if (!token || !user) {
      localStorage.removeItem("singhaniaDashboardState");
      return;
    }
    localStorage.setItem("singhaniaDashboardState", JSON.stringify({ token, user, brand, reportType, filters }));
  }, [token, user, brand, reportType, filters]);

  useEffect(() => {
    if (token && user && brand && !report && !loading) {
      loadReport(brand, filters, reportType);
    }
  }, []);

  async function loadReport(nextBrand, nextFilters, nextReportType) {
    setReport(null);
    setError("");
    setLoading(true);
    try {
      setReport(
        await api(
          "/api/report",
          {
            brand: nextBrand,
            filters: nextFilters || {},
            reportType: nextReportType || reportType,
          },
          token,
        ),
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function selectBrand(nextBrand) {
    setBrand(nextBrand);
    setFilters({});
    setReportType("location");
    await loadReport(nextBrand, {}, "location");
  }

  async function changeReportType(nextType) {
    setReportType(nextType);
    await loadReport(brand, filters, nextType);
  }

  function logout() {
    localStorage.removeItem("singhaniaDashboardState");
    setToken("");
    setUser(null);
    setBrand("");
    setReportType("location");
    setReport(null);
    setFilters({});
  }

  if (!user) return <Login onLogin={onLogin} />;

  return (
    <>
      <Header
        user={user}
        brand={brand}
        onBack={() => {
          setBrand("");
          setReportType("location");
          setReport(null);
          setFilters({});
        }}
        onLogout={logout}
      />
      {!brand ? <BrandSelection user={user} onSelect={selectBrand} /> : null}
      {error ? (
        <main>
          <div className="error">{error}</div>
        </main>
      ) : null}
      {loading && !report ? (
        <main>
          <div className="loading">Loading report...</div>
        </main>
      ) : null}
      {report ? (
        <Report
          report={report}
          reportType={reportType}
          onReportTypeChange={changeReportType}
          filters={filters}
          loading={loading}
          onFilterChange={setFilters}
          onApplyFilters={() => loadReport(brand, filters, reportType)}
          onResetFilters={() => {
            setFilters({});
            loadReport(brand, {}, reportType);
          }}
        />
      ) : null}
    </>
  );
}
