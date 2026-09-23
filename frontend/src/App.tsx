import Navbar from "./components/layout/Navbar";
import Chat from "./pages/Chat";
import Docs from "./pages/Docs";
import Home from "./pages/Home";
import Settings from "./pages/Settings";
import { useEffect, useState } from "react";

function App() {
  const [path, setPath] = useState(window.location.pathname);

  useEffect(() => {
    const updatePath = () => setPath(window.location.pathname);
    window.addEventListener("popstate", updatePath);
    const storedTheme = localStorage.getItem("docdrift-theme");
    if (storedTheme === "Dark" || storedTheme === "Light") {
      document.documentElement.classList.add(storedTheme === "Dark" ? "theme-dark" : "theme-light");
    }
    return () => window.removeEventListener("popstate", updatePath);
  }, []);

  const isChat = path === "/chat";
  const isDocs = path === "/docs";
  const isSettings = path === "/settings";
  const activePage = isChat ? "Chat" : isDocs ? "Docs" : isSettings ? "Settings" : "Home";

  return (
    <div className="app">
      <Navbar activePage={activePage} />
      {isChat ? <Chat /> : isDocs ? <Docs /> : isSettings ? <Settings /> : <Home />}
    </div>
  );
}

export default App;