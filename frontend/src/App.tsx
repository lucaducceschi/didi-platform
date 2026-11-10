import { Link, NavLink, Navigate, Route, Routes } from 'react-router'
import { useAuth } from './auth'
import { ErrorMessage } from './components/Message'
import { ThemeToggle } from './components/ThemeToggle'
import { AccountPage } from './pages/AccountPage'
import { ArticlePage } from './pages/ArticlePage'
import { TopicsPage } from './pages/TopicsPage'
import { CorpusAnalyticsPage } from './pages/CorpusAnalyticsPage'
import { DashboardPage } from './pages/DashboardPage'
import { LoginPage } from './pages/LoginPage'
import { ProjectPage } from './pages/ProjectPage'
import { ProjectsPage } from './pages/ProjectsPage'
import { SearchPage } from './pages/SearchPage'
import { UsersPage } from './pages/UsersPage'

export function App() {
  const { user, checking, error, logout } = useAuth()

  return (
    <>
      <header className="app-header">
        <div className="app-nav">
          <Link to="/" className="app-title">DIDI Platform</Link>
          {user && (
            <nav aria-label="Main">
              <NavLink to="/" end>Dashboard</NavLink>
              <NavLink to="/projects">Projects</NavLink>
              <NavLink to="/search">Corpus search</NavLink>
              <NavLink to="/analytics">Macro analytics</NavLink>
              <NavLink to="/topics">Topics</NavLink>
              {user.is_admin && <NavLink to="/users">Users</NavLink>}
            </nav>
          )}
        </div>
        <div className="row">
          {user && <NavLink to="/account">{user.display_name}</NavLink>}
          {user && <button type="button" className="button-quiet" onClick={() => void logout()}>Log out</button>}
          <ThemeToggle />
        </div>
      </header>
      <main className="app-main">
        {checking ? <p className="result-count">Loading…</p> : !user ? (
          <>
            <ErrorMessage error={error} />
            <LoginPage />
          </>
        ) : (
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/projects" element={<ProjectsPage />} />
            <Route path="/projects/:projectId/*" element={<ProjectPage />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/analytics" element={<CorpusAnalyticsPage />} />
            <Route path="/topics" element={<TopicsPage />} />
            <Route path="/articles/:id" element={<ArticlePage />} />
            <Route path="/account" element={<AccountPage />} />
            <Route path="/users" element={user.is_admin ? <UsersPage /> : <Navigate to="/projects" replace />} />
            <Route path="*" element={<p className="message">This page does not exist. <Link to="/projects">Go to projects</Link></p>} />
          </Routes>
        )}
      </main>
    </>
  )
}
