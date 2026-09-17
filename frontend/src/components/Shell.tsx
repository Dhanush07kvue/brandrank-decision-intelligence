import { ReactNode, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { ContextBar } from './ContextBar'
import kenvueLogo from '../assets/logo/Kenvue_Symbol_Black_RGB.png'
import overviewIcon from '../assets/icons/Kenvue_Icon_Standard_Black_Dashboard.svg'
import signalsIcon from '../assets/icons/Kenvue_Icon_Standard_Black_Data_Chart.svg'
import decisionsIcon from '../assets/icons/Kenvue_Icon_Standard_Black_Checklist.svg'
import interventionsIcon from '../assets/icons/Kenvue_Icon_Standard_Black_Purpose_Driven_Target.svg'
import outcomesIcon from '../assets/icons/Kenvue_Icon_Standard_Black_Line_Graph.svg'
import trustIcon from '../assets/icons/Kenvue_Icon_Standard_Black_Shield_with_Checkmark.svg'
import assistantIcon from '../assets/icons/Kenvue_Icon_Standard_Black_One_Speech_Bubble.svg'
import settingsIcon from '../assets/icons/Kenvue_Icon_Standard_Black_Cogwheel_Settings.svg'
import evidenceIcon from '../assets/icons/Kenvue_Icon_Standard_Black_Book.svg'

type ShellProps = {
  children: ReactNode
}

export function Shell({ children }: ShellProps) {
  const location = useLocation()
  const [sidebarOpen, setSidebarOpen] = useState(true)

  const navItems = [
    { path: '/', label: 'Overview', icon: overviewIcon },
    { path: '/signals', label: 'Signals', icon: signalsIcon },
    { path: '/decisions', label: 'Decisions', icon: decisionsIcon },
    { path: '/interventions', label: 'Interventions', icon: interventionsIcon },
    { path: '/outcomes', label: 'Outcomes', icon: outcomesIcon },
    { path: '/data-trust', label: 'Data Trust', icon: trustIcon },
    { path: '/ingestion', label: 'Ingestion & Ontology', icon: trustIcon },
    { path: '/evidence', label: 'Evidence', icon: evidenceIcon },
    { path: '/assistant', label: 'Assistant', icon: assistantIcon },
    { path: '/settings', label: 'Settings', icon: settingsIcon },
  ]

  const isActive = (path: string) => location.pathname === path

  return (
    <div className="app-shell flex flex-col min-h-screen bg-slate-50">
      <header className="top-bar flex justify-between items-center bg-gradient-to-r from-brand-secondary to-brand-primary text-white p-4 shadow-md z-50">
        <div className="top-bar-left flex items-center gap-4">
          <button
            className="sidebar-toggle p-2 hover:bg-white/10 rounded-full transition-colors"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            aria-label="Toggle sidebar"
          >
            {sidebarOpen ? '✕' : '☰'}
          </button>
          <img
            className="kenvue-logo h-10 object-contain filter brightness-0 invert"
            src={kenvueLogo}
            alt="Kenvue logo"
          />
          <div>
            <h1 className="text-xl font-extrabold tracking-tight m-0">Kenvue Decision Intelligence</h1>
            <p className="text-sm opacity-90 m-0">Enterprise Leadership View</p>
          </div>
        </div>
      </header>
      <ContextBar />

      <div className="main-layout">
        {/* Sidebar */}
        {sidebarOpen && (
          <nav className="sidebar">
            <div className="nav-section">
              {navItems.map((item) => (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`nav-item ${isActive(item.path) ? 'active' : ''}`}
                >
                  <img className="nav-icon" src={item.icon} alt="" aria-hidden="true" />
                  <span className="nav-label">{item.label}</span>
                </Link>
              ))}
            </div>
          </nav>
        )}

        {/* Content */}
        <main className="content">
          {children}
          <footer className="app-footer">
            <img
              className="kenvue-footer-logo"
              src={kenvueLogo}
              alt="Kenvue logo"
            />
            <div>
              <strong></strong>
              <span>AEO GEO Insights platform</span>
            </div>
          </footer>
        </main>
      </div>
    </div>
  )
}
