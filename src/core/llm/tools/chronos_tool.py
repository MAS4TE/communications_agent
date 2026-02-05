# core/llm/tools/chronos_tool.py

from core.llm.tools.decorators import tool, trace_tool
from configs.settings import Settings
import pandas as pd
import requests

settings = Settings()

def forecast_from_csv(
    csv_path: str,
    start,
    end,
    history_days: int = 1,
    timestamp_col: str = "datetime",
    value_col: str = None,
):
    """
    Reads CSV, builds Chronos history[], calls Chronos, and returns full response.
    Prints debug info at each step.
    """
    print("=== forecast_from_csv ===")
    print("csv_path:", csv_path)
    print("start:", start, "end:", end)
    print("history_days:", history_days)

    # 1. Load CSV
    print("Loading CSV...")
    df = (
        pd.read_csv(csv_path, parse_dates=[timestamp_col])
        .set_index(timestamp_col)
        .sort_index()
    )
    print("DF info:")
    print(df.info())
    print(df.head())

    # 2. Infer forecast horizon
    # Ensure both index and bounds are tz-aware UTC
    df.index = pd.to_datetime(df.index, utc=True)
    start = pd.to_datetime(start, utc=True)
    end = pd.to_datetime(end, utc=True)

    print("Inferring forecast horizon...")
    horizon_df = df.loc[start:end]
    horizon = len(horizon_df)
    print("Horizon length:", horizon)

    if horizon <= 0:
        raise ValueError("Forecast window does not overlap data")

    # 3. Slice history window
    print("Preparing history window...")
    history_start = start - pd.Timedelta(days=history_days)
    history_df = df.loc[history_start:start]
    print("History rows:", len(history_df))
    print(history_df.head())

    # 4. Build Chronos history payload
    print("Building Chronos payload...")
    history = [
        {"timestamp": ts.isoformat(), "value": float(v)}
        for ts, v in zip(history_df.index, history_df[value_col])
    ]
    print("History sample:", history[:3])
    print("History length:", len(history))

    payload = {"history": history, "prediction_length": horizon}
    print("Payload keys:", payload.keys())
    print("Prediction length:", horizon)

    # 5. Call Chronos
    print("Calling Chronos...")
    r = requests.post(
        f"{settings.CHRONOS_URL}/forecast",
        json=payload,
        timeout=settings.CHRONOS_TIMEOUT,
    )
    print("Chronos status:", r.status_code)
    r.raise_for_status()
    response = r.json()
    print("Chronos response keys:", response.keys())
    print("Median sample:", response["median"][:5])

    # 6. Build correct forecast timestamps
    print("Building forecast timestamps...")
    freq = pd.infer_freq(df.index)
    if freq is None:
        print("Could not infer frequency from CSV index, defaulting to 15min")
        freq = "15T"  # fallback

    forecast_index = pd.date_range(start=end, periods=len(response["median"]), freq=freq)
    print("Forecast timestamps sample:", forecast_index[:5])

    return {
        "median": response["median"],
        "timestamps": forecast_index.astype(str).tolist()
    }

    


def save_median_forecast(result, filename="data/forecast_output.csv"):
    """
    Converts Chronos median forecast into a CSV with timestamps from the real data.
    """
    print('save median forecast')
    median = result["median"]
    timestamps = pd.to_datetime(result["timestamps"])  # real 15-min timestamps

    df = pd.DataFrame({
        "timestamp": timestamps,
        "median": median
    })
    df.to_csv(filename, index=False)
    print(f"Forecast saved to {filename}")
    return filename



@tool(
    schema={
        "type": "function",
        "function": {
            "name": "forecast_timeseries_from_csv",
            "description": (
                "Forecast a numeric time series (demand, price, solar, etc.) "
                "from a CSV using Chronos. Returns median only."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "csv_path": {"type": "string"},
                    "start": {"type": "string", "description": "ISO datetime"},
                    "end": {"type": "string", "description": "ISO datetime"},
                    "history_days": {"type": "number", "default": 30},
                    "value_col": {"type": "string", "default": "load_kw"},
                    "save_csv": {"type": "boolean", "default": True},
                    "csv_filename": {"type": "string", "default": "forecast_output.csv"},
                },
                "required": ["csv_path", "start", "end"],
            },
        },
    }
)
@trace_tool
def forecast_timeseries_from_csv(
    csv_path: str,
    start: str,
    end: str,
    history_days: int = 1,
    value_col: str = None,
    save_csv: bool = True,
    csv_filename: str = "forecast_output.csv",
):
    """
    Tool wrapper: calls forecast_from_csv and returns median forecast.
    Optionally saves the median to a CSV.
    """
    print('forecast timeseries from csv')
    response = forecast_from_csv(
        csv_path=csv_path,
        start=start,
        end=end,
        history_days=history_days,
        value_col=value_col,
    )

    # print("received response key")

    if save_csv:
        # print('in if')
        save_median_forecast(result=response, filename=csv_filename)

    # print("after save csv")

    return {
        "median": response["median"],
        "timestamps": pd.date_range(
            start=start,
            periods=len(response["median"]),
            freq="15T"  # or infer from your CSV
        ).astype(str).tolist()
}

