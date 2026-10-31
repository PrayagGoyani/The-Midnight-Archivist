import React, { useState } from 'react';
import { NavLink, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import {
  FolderArchive,
  Feather,
  BookOpen,
  Library,
  Sliders,
  Menu,
  X,
} from 'lucide-react';
import Archive from './pages/Archive';
import WritingDesk from './pages/WritingDesk';
import ReadingRoom from './pages/ReadingRoom';
import StoryShelf from './pages/StoryShelf';
import Settings from './pages/Settings';
import './styles/app.css';

const navItems = [
  { to: '/archive', label: 'Archive', icon: FolderArchive },
  { to: '/write', label: 'Writing Desk', icon: Feather },
  { to: '/read', label: 'Reading Room', icon: BookOpen },
  { to: '/shelf', label: 'Story Shelf', icon: Library },
  { to: '/settings', label: 'Settings', icon: Sliders },
];

export default function App() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const location = useLocation();

  // Close mobile drawer when route changes
  React.useEffect(() => {
    setMobileMenuOpen(false);
  }, [location.pathname]);

  return (
    <div className="app-shell">
      {/* Mobile Header Bar */}
      <header className="mobile-header">
        <NavLink to="/archive" className="mobile-logo">
          Midnight Archivist
        </NavLink>
        <button
          type="button"
          className="mobile-menu-btn"
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          aria-expanded={mobileMenuOpen}
          aria-label={mobileMenuOpen ? 'Close navigation menu' : 'Open navigation menu'}
        >
          {mobileMenuOpen ? <X size={22} /> : <Menu size={22} />}
        </button>
      </header>

      {/* Navigation Rail / Drawer */}
      <nav
        className={`nav-rail ${mobileMenuOpen ? 'mobile-open' : ''}`}
        aria-label="Main Navigation"
      >
        <div className="nav-header">
          <NavLink to="/archive" className="logo">
            Midnight Archivist
          </NavLink>
          <span className="logo-tagline">A quiet place for stories that linger.</span>
        </div>

        <ul className="nav-list">
          {navItems.map((item) => {
            const IconComponent = item.icon;
            return (
              <li key={item.to} className="nav-item">
                <NavLink
                  to={item.to}
                  className={({ isActive }) =>
                    isActive ? 'nav-link active' : 'nav-link'
                  }
                >
                  <IconComponent size={18} className="nav-link-icon" />
                  <span>{item.label}</span>
                </NavLink>
              </li>
            );
          })}
        </ul>

        <div className="nav-footer">
          <span>Ollama & SQLite Powered</span>
        </div>
      </nav>

      {/* Mobile backdrop */}
      {mobileMenuOpen && (
        <div
          className="mobile-backdrop"
          onClick={() => setMobileMenuOpen(false)}
          role="presentation"
        />
      )}

      {/* Main Content Area */}
      <main className="main-content" id="main-content">
        <Routes>
          <Route path="/" element={<Navigate to="/archive" replace />} />
          <Route path="/archive" element={<Archive />} />
          <Route path="/write" element={<WritingDesk />} />
          <Route path="/read" element={<ReadingRoom />} />
          <Route path="/read/:storyId" element={<ReadingRoom />} />
          <Route path="/shelf" element={<StoryShelf />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
    </div>
  );
}
