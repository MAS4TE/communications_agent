# def forecast_from_csv(
#     csv_path: str,
#     start,
#     end,
#     history_days: int = 1,
#     timestamp_col: str = "datetime",
#     value_col: str = "load_kw",
# ):
#     import pandas as pd
#     import requests
#     from configs.settings import Settings

#     settings = Settings()

#     print("=== forecast_from_csv ===")
#     print("csv_path:", csv_path)
#     print("start:", start, "end:", end)

#     # 1. Load data
#     print("loading CSV")
#     df = (
#         pd.read_csv(csv_path, parse_dates=[timestamp_col])
#         .set_index(timestamp_col)
#         .sort_index()
#     )

#     print("df info:")
#     print(df.info())
#     print(df.head())

#     # 2. Infer forecast horizon
#     print("inferring forecast horizon")
#     horizon_df = df.loc[start:end]
#     horizon = len(horizon_df)
#     print("horizon:", horizon)

#     if horizon <= 0:
#         raise ValueError("Forecast window does not overlap data")

#     # 3. Slice history window
#     print("preparing history window")
#     history_start = start - pd.Timedelta(days=history_days)
#     history_df = df.loc[history_start:start]

#     print("history rows:", len(history_df))
#     print(history_df.head())

#     # 4. Build Chronos history payload
#     print("building Chronos history payload")
#     history = [
#         {
#             "timestamp": ts.isoformat(),
#             "value": float(v),
#         }
#         for ts, v in zip(history_df.index, history_df[value_col])
#     ]

#     print("history sample:", history[:3])
#     print("history length:", len(history))

#     payload = {
#         "history": history,
#         "prediction_length": horizon,
#     }

#     print("payload keys:", payload.keys())
#     print("prediction_length:", horizon)

#     # 5. Call Chronos
#     print("calling Chronos")
#     r = requests.post(
#         f"{settings.CHRONOS_URL}/forecast",
#         json=payload,
#         timeout=settings.CHRONOS_TIMEOUT,
#     )

#     print("Chronos status:", r.status_code)
#     r.raise_for_status()

#     response = r.json()
#     print("Chronos response keys:", response.keys())

#     return response
