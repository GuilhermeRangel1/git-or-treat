import { Navigate, Route, Routes } from "react-router-dom";
import {
  PanoramaPage,
  ReceitaPage,
  UC360Page,
  InspecoesPage,
  OrdensPage,
  OperacaoPage,
  AssistentePage,
} from "./pages/index.ts";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/panorama" replace />} />
      <Route path="/panorama" element={<PanoramaPage />} />
      <Route path="/receita" element={<ReceitaPage />} />
      <Route path="/uc-360" element={<UC360Page />} />
      <Route path="/inspecoes" element={<InspecoesPage />} />
      <Route path="/ordens" element={<OrdensPage />} />
      <Route path="/operacao" element={<OperacaoPage />} />
      <Route path="/assistente" element={<AssistentePage />} />
      <Route path="*" element={<Navigate to="/panorama" replace />} />
    </Routes>
  );
}
