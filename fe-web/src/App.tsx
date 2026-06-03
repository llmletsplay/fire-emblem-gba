import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import Home from "./pages/Home";
import About from "./pages/About";
import Data from "./pages/Data";
import Benchmarks from "./pages/Benchmarks";
import Docs from "./pages/Docs";
import "./App.css";

function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <nav className="navbar">
          <div className="nav-brand">
            <span className="brand-icon">FE</span>
            <span className="brand-text">Fire Emblem AI</span>
          </div>
          <div className="nav-links">
            <NavLink
              to="/"
              className={({ isActive }) => (isActive ? "active" : "")}
            >
              Home
            </NavLink>
            <NavLink
              to="/about"
              className={({ isActive }) => (isActive ? "active" : "")}
            >
              About
            </NavLink>
            <NavLink
              to="/data"
              className={({ isActive }) => (isActive ? "active" : "")}
            >
              Data
            </NavLink>
            <NavLink
              to="/benchmarks"
              className={({ isActive }) => (isActive ? "active" : "")}
            >
              Benchmarks
            </NavLink>
            <NavLink
              to="/docs"
              className={({ isActive }) => (isActive ? "active" : "")}
            >
              Docs
            </NavLink>
          </div>
        </nav>
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/about" element={<About />} />
            <Route path="/data" element={<Data />} />
            <Route path="/benchmarks" element={<Benchmarks />} />
            <Route path="/docs" element={<Docs />} />
          </Routes>
        </main>
        <footer className="footer">
          <p>Fire Emblem AI - LLM-Powered Gameplay</p>
          <p>
            <a
              href="https://github.com/llmletsplay/fire-emblem-gba"
              target="_blank"
              rel="noreferrer"
            >
              GitHub
            </a>
          </p>
        </footer>
      </div>
    </BrowserRouter>
  );
}

export default App;
