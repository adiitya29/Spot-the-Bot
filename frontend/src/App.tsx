import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Join } from "./pages/Join";
import { Landing } from "./pages/Landing";
import { Room } from "./pages/Room";

const queryClient = new QueryClient();

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/join/:code" element={<Join />} />
          <Route path="/r/:code" element={<Room />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
