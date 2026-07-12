import { Outlet, Route, Routes, useParams } from "react-router-dom";

import { Header } from "@/components/Header";
import { Message } from "@/components/Message";
import { Home } from "@/pages/Home";
import { Library } from "@/pages/Library";
import { GameDetail } from "@/pages/GameDetail";
import { NotFound } from "@/pages/NotFound";
import { isSteamId64 } from "@/lib/steamid";

// Ponto único por onde passa toda URL com steamid: barrando aqui, as páginas
// filhas nunca montam com um id malformado e não precisam saber que ele existe.
function SteamIdValido() {
  const { steamid = "" } = useParams();
  if (!isSteamId64(steamid))
    return (
      <Message role="alert">Steam ID inválido. Ele deve ter 17 dígitos.</Message>
    );
  return <Outlet />;
}

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
          <Route path="/u/:steamid" element={<SteamIdValido />}>
            <Route index element={<Library />} />
            <Route path="game/:appid" element={<GameDetail />} />
          </Route>
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
