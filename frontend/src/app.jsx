import { Routes, Route }
from "react-router-dom";

import Home
from "./pages/Home.jsx";

import Analysis
from "./pages/Analysis.jsx";

function App() {

  return (

    <Routes>

      <Route
        path="/"
        element={<Home />}
      />

      <Route
        path="/analysis"
        element={<Analysis />}
      />

    </Routes>

  );

}

export default App;