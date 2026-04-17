import { useState }
from "react";

import { useNavigate }
from "react-router-dom";

function Home() {

  const [file, setFile] =
    useState(null);

  const [repo, setRepo] =
    useState("");

  const navigate =
    useNavigate();

  const scanZip =
    async () => {

    const formData =
      new FormData();

    formData.append(
      "file",
      file
    );

    const res =
      await fetch(
        "http://127.0.0.1:8000/scan-zip",
        {
          method: "POST",
          body: formData
        }
      );

    const data =
      await res.json();

    navigate(
      "/analysis",
      { state: data }
    );

  };

  const scanRepo =
    async () => {

    const formData =
      new FormData();

    formData.append(
      "repo_url",
      repo
    );

    const res =
      await fetch(
        "http://127.0.0.1:8000/scan-repo",
        {
          method: "POST",
          body: formData
        }
      );

    const data =
      await res.json();

    navigate(
      "/analysis",
      { state: data }
    );

  };

  return (

    <div className="container">

      <h1>
        Technical Debt Advisor
      </h1>

      <div className="card">

        <h2>
          Upload ZIP
        </h2>

        <input
          type="file"
          accept=".zip"
          onChange={(e)=>
            setFile(
              e.target.files[0]
            )
          }
        />

        <button
          onClick={scanZip}
        >
          Scan ZIP
        </button>

      </div>

      <div className="card">

        <h2>
          Repo URL
        </h2>

        <input
          type="text"
          placeholder="GitHub repo"
          value={repo}
          onChange={(e)=>
            setRepo(
              e.target.value
            )
          }
        />

        <button
          onClick={scanRepo}
        >
          Scan Repo
        </button>

      </div>

    </div>

  );

}

export default Home;