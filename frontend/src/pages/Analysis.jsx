import { useLocation }
from "react-router-dom";

function Analysis() {

  const location =
    useLocation();

  const result =
    location.state;

  if (!result)
    return <div>No Data</div>;

  return (

    <div className="container">

      <h1>
        Analysis Report
      </h1>

      <h2>
        Score:
        {result.overall_score}
      </h2>

      {result.files.map(
        (f,i)=>(

        <div
          key={i}
          className="fileBox"
        >

          <h3>
            {f.file}
          </h3>

          <p>
            Score:
            {f.file_score}
          </p>

          {f.smells.map(
            (s,j)=>(

              <div
                key={j}
                className="smellBox"
              >

                <h4>
                  {s.name}
                </h4>

                <p>
                  {s.explanation}
                </p>

                <p>
                  {s.suggestion}
                </p>

              </div>

            )
          )}

        </div>

      ))}

    </div>

  );

}

export default Analysis;