import { Navigate, Route, BrowserRouter, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { AgentEditorPage } from "./pages/AgentEditorPage";
import { AgentPage } from "./pages/AgentPage";
import { ChatPage } from "./pages/ChatPage";
import { DiscoverPage } from "./pages/DiscoverPage";
import { TemplateDetailPage } from "./pages/TemplateDetailPage";

function App() {
  return (
    <BrowserRouter>
      <AppShell>
        <Routes>
          <Route path="/" element={<Navigate to="/chat" replace />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/discover" element={<DiscoverPage />} />
          <Route path="/templates/:name" element={<TemplateDetailPage />} />
          <Route path="/agents/:agentId" element={<AgentPage />} />
          <Route path="/agents/:agentId/edit" element={<AgentEditorPage />} />
        </Routes>
      </AppShell>
    </BrowserRouter>
  );
}

export default App;
