import { Navigate, Route, BrowserRouter, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { ChatPage } from "./pages/ChatPage";
import { DiscoverPage } from "./pages/DiscoverPage";
import { ReportsPage } from "./pages/ReportsPage";

function App() {
  return (
    <BrowserRouter>
      <AppShell>
        <Routes>
          <Route path="/" element={<Navigate to="/chat" replace />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/discover" element={<DiscoverPage />} />
          <Route path="/reports" element={<ReportsPage />} />
        </Routes>
      </AppShell>
    </BrowserRouter>
  );
}

export default App;
