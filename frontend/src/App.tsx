import { Link, Route, Routes } from 'react-router'
import { ThemeToggle } from './components/ThemeToggle'
import { ArticlePage } from './pages/ArticlePage'
import { SearchPage } from './pages/SearchPage'

export function App() {
  return (
    <>
      <header className="app-header">
        <Link to="/" className="app-title">DIDI Platform</Link>
        <ThemeToggle />
      </header>
      <main className="app-main">
        <Routes>
          <Route path="/" element={<SearchPage />} />
          <Route path="/articles/:id" element={<ArticlePage />} />
          <Route path="*" element={<p className="message">This page does not exist. <Link to="/">Go to search</Link></p>} />
        </Routes>
      </main>
    </>
  )
}
