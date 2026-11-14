import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Join } from "./pages/Join";
import { Landing } from "./pages/Landing";
import { ReplayPlay } from "./pages/ReplayPlay";
import { Replays } from "./pages/Replays";
import { Room } from "./pages/Room";
import { Share } from "./pages/Share";

const queryClient = new QueryClient();

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/join/:code" element={<Join />} />
          <Route path="/r/:code" element={<Room />} />
          <Route path="/replays" element={<Replays />} />
          <Route path="/replays/:id" element={<ReplayPlay />} />
          <Route path="/share/:code" element={<Share />} />
          <Route path="/s/:code" element={<Share />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
