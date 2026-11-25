import React from "react"
import ReactDOM from "react-dom/client"
import App, { ErrorBoundary } from "./App"
import "./styles.css"

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {/* Root boundary: catches a throw from App's own render, which the
        in-app boundary cannot see. */}
    <ErrorBoundary onReset={() => window.location.reload()}>
      <App />
    </ErrorBoundary>
  </React.StrictMode>,
)
