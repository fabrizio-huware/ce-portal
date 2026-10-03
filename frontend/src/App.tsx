import { useEffect, useState } from "react";

type Status = "loading" | "ok" | "error";

// Schermata provvisoria: verifica la comunicazione con le API.
// Il design definitivo (brand Huware) arriva nello Step 8.
export default function App() {
  const [status, setStatus] = useState<Status>("loading");

  useEffect(() => {
    fetch("/api/v1/health")
      .then((r) => (r.ok ? setStatus("ok") : setStatus("error")))
      .catch(() => setStatus("error"));
  }, []);

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: "2rem" }}>
      <h1>Portale Conti Economici</h1>
      <p>
        Stato API:{" "}
        <strong>
          {status === "loading" && "verifica in corso…"}
          {status === "ok" && "raggiungibile"}
          {status === "error" && "non raggiungibile"}
        </strong>
      </p>
    </main>
  );
}
