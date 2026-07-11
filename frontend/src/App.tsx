import { Route, Routes } from "react-router-dom";

import { Header } from "@/components/Header";
import { Home } from "@/pages/Home";
import { Library } from "@/pages/Library";
import { GameDetail } from "@/pages/GameDetail";
import { NotFound } from "@/pages/NotFound";

function App() {
  return (
    <div className="min-h-screen">
      <a
        href="#conteudo"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-[60] focus:rounded focus:bg-primary focus:px-3 focus:py-2 focus:text-primary-foreground"
      >
        Pular para o conteúdo
      </a>
      <Header />
      <main id="conteudo" className="mx-auto max-w-6xl p-6">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/u/:steamid" element={<Library />} />
          <Route path="/u/:steamid/game/:appid" element={<GameDetail />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
