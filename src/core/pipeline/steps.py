# core/pipeline/steps.py
from core.llm.tools.registry import tool_registry
from core.main_context import GLOBAL_PROFILE_ID
from core.main_context import get_mqtt_agent


import pandas as pd
from datetime import datetime

# from core.domain.simple_forecast import forecast_from_csv
from core.llm.tools.chronos_tool import forecast_timeseries_from_csv


def retrieve_step_map():
    return STEP_MAP



"""
STEPS AFTER MARKET OPENING TO SUBMIT A BID
"""

async def step1(data):
    data["step1"] = "done"
    print("STEPS : Step 1 completed")
    return data

# core/pipeline/steps_market.py
async def step_market_open(data):
    # if data.get("event") == "market_open":
    print("PIPELINE: Market opened step triggered!")
    # print market_data
    print('market data', data["market_data"])
    data["market_open_processed"] = True
    return data

async def step_retrieve_market_info(data):
    market_info = data["market_data"]
    products = market_info.get("products", [])
    starts = []
    ends = []
    for p in products:
        if "start_time" in p and "end_time" in p: 
            starts.append(pd.to_datetime(p["start_time"]))
            ends.append(pd.to_datetime(p["end_time"]))

    data['market_window'] = {"start": starts[0], "end":ends[0]} # only take the first product for now
    print('market window ', data["market_window"])

    return data


async def step_fc_demand(data):
    print("in step fc demand")

    # from core.llm.tools.chronos_tool import forecast_timeseries_from_csv

    start = pd.to_datetime(data["market_window"]["start"])
    end = pd.to_datetime(data["market_window"]["end"])

    # Call the tool
    demand_fc = forecast_timeseries_from_csv(
        csv_path="data/profile_data/profile_3_demand.csv",
        start=start,
        end=end,
        history_days=1,
        value_col="load_kw",
        save_csv=True,
        csv_filename="data/demand_forecast_test1.csv"
    )

    print('chronos returned, length: ', len(demand_fc["median"]))

    timestamps = list(demand_fc["timestamps"])

    # Step 2: convert with errors='raise' to see any problem
    timestamps = pd.to_datetime(timestamps, errors='raise')

    # Step 3: build Series
    demand_series = pd.Series(demand_fc["median"], index=timestamps)

    data["demand_fc"] = demand_series

    print("STEPS: demand section WITH forecast")
    print(demand_series)

    return data

async def step_fc_solar(data):  
    start = data["market_window"]["start"]
    end = data["market_window"]["end"]

    # Call the tool
    solar_fc = forecast_timeseries_from_csv(
        csv_path="data/profile_data/profile_3_solar.csv",
        start=start,
        end=end,
        history_days=1,
        value_col="solar_kw",
        save_csv=True,
        csv_filename="data/solar_forecast_test1.csv"
    )

    print('chronos returned, length: ', len(solar_fc["median"]))

    timestamps = list(solar_fc["timestamps"])

    # Step 2: convert with errors='raise' to see any problem
    timestamps = pd.to_datetime(timestamps, errors='raise')

    # Step 3: build Series
    solar_series = pd.Series(solar_fc["median"], index=timestamps)

    data["solar_fc"] = solar_series

    print("STEPS: solar WITH forecast")
    print(solar_series)

    return data

# async def step_fc_prices(data): # currently without forecasts!
#     start = data["market_window"]["start"]
#     end = data["market_window"]["end"]

#     # Als tz-naïef → UTC localize
#     if start.tzinfo is None:
#         start = start.tz_localize("UTC")
#     if end.tzinfo is None:
#         end = end.tz_localize("UTC")

#     df = pd.read_csv("data/profile_data/prices.csv")

#     if df.columns[0] == "Unnamed: 0":
#         df = df.drop(columns=df.columns[0])

#     df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
#     df = df.set_index("datetime")


#     price_data = df.loc[start:end]
#     data["prices_fc"] = {col: price_data[col] for col in price_data.columns}

#     print('STEPS: prices section for market start and end time -- without FC!')

#     return data

async def step_fc_prices(data):
    print("in step fc prices")

    start = pd.to_datetime(data["market_window"]["start"])
    end = pd.to_datetime(data["market_window"]["end"])

    price_csv = "data/profile_data/prices.csv"

    # Read once to discover columns
    df = pd.read_csv(price_csv)

    if df.columns[0] == "Unnamed: 0":
        df = df.drop(columns=df.columns[0])

    # Assume first column is datetime
    timestamp_col = "datetime"
    price_columns = [c for c in df.columns if c != timestamp_col]

    prices_fc = {}

    for col in price_columns:
        print(f"Forecasting price column: {col}")

        price_fc = forecast_timeseries_from_csv(
            csv_path=price_csv,
            start=start,
            end=end,
            history_days=1,
            value_col=col,          # this is the key: different column each time
            save_csv=True,
            csv_filename=f"data/{col}_forecast_test.csv"
        )

        print(f"Chronos returned {len(price_fc['median'])} points for {col}")

        timestamps = pd.to_datetime(price_fc["timestamps"], errors="raise")
        series = pd.Series(price_fc["median"], index=timestamps)

        prices_fc[col] = series

    data["prices_fc"] = prices_fc

    print("STEPS: prices section WITH forecast")
    for k, v in prices_fc.items():
        print(k, v.head())

    return data



async def step_battery_utility_calculator(data):
    print("STEPS buc: tool")

    tool_get_profile = next(t for t in tool_registry.tools if t.__name__ == "get_profile_metadata")
    result_profile = tool_get_profile(GLOBAL_PROFILE_ID)
    data["storage_size_kwh"] = result_profile.get("battery_size_kwh", 0.0)

    def to_1d(x):
        if x is None:
            return None

        # DataFrame → take FIRST column explicitly
        if isinstance(x, pd.DataFrame):
            if x.shape[1] != 1:
                raise ValueError(f"Expected single-column DataFrame, got {x.shape}")
            series = x.iloc[:, 0]
        # Series → OK
        elif isinstance(x, pd.Series):
            series = x
        # ndarray → flatten safely
        elif hasattr(x, "ndim"):
            series = pd.Series(x)
        # list → Series
        else:
            series = pd.Series(x)
        
        # Remove timezone if present to ensure compatibility
        if isinstance(series, pd.Series) and hasattr(series.index, 'tz') and series.index.tz is not None:
            series = series.copy()
            series.index = series.index.tz_localize(None)
        
        return series

    
    demand_series = to_1d(data.get("demand_fc"))
    solar_series  = to_1d(data.get("solar_fc"))

    # Convert prices to Series with the same index as demand
    # index = solar_series.index if isinstance(solar_series, pd.Series) else None

    grid_prices      = to_1d(data.get("prices_fc", {}).get("supplier"))
    eeg_prices       = to_1d(data.get("prices_fc", {}).get("eeg"))
    community_prices = to_1d(data.get("prices_fc", {}).get("community"))
    wholesale_prices = to_1d(data.get("prices_fc", {}).get("wholesale"))

    print('buc all inputs ready')

    # Find the buc tool in the registry
    tool = next(t for t in tool_registry.tools if t.__name__ == "battery_utility_calculator")

    result = tool(
        storage_size_kwh = data.get('storage_size_kwh', 0), #default 0kWh if not set
        # storage_size_kwh = 5,
        demand_series    = demand_series,
        solar_series     = solar_series,
        grid_prices      = grid_prices,
        eeg_prices       = eeg_prices,
        community_prices = community_prices,
        wholesale_prices = wholesale_prices,
        )
    
    # Take first step of bidding curve
    first_step = {k: v[0] for k, v in result['bidding_curve'].items()}
    bid_volume = first_step['volume']
    bid_price = first_step['marginal_price']
    data['bid_volume']=bid_volume
    data['bid_price']=bid_price


    # print('STEPS: BUC')
    print('buc result: ', result)
    print('STEPS: vol ', bid_volume, ' price ', bid_price)
    return data

async def step_publish_bid(data):
    print('in step publish bid')
    bid_volume = data.get("bid_volume")
    bid_price = data.get("bid_price")

    if data.get("bid_id") is None:
        print('if')
        data["bid_id"] = 0      
    else:
        print('else')
        data["bid_id"] += 1 

    mqtt_agent = get_mqtt_agent()
    mqtt_agent.send_bid_to_market(data["bid_id"], bid_price, bid_volume)

    print('step publish successful')
    return data
    

async def time_tool_step(data):
    # Print tools for debugging
    print("Tools in registry:")
    for t in tool_registry.tools:
        print("-", t.__name__)
    
    # Find the time tool
    tool = next(t for t in tool_registry.tools if t.__name__ == "get_current_time")
    result = tool()
    data["current_time"] = result["current_time"]
    return data

async def step2(data):
    print("Step 2 sees current_time:", data.get("current_time"))
    data["step2"] = "done"
    print("STEPS : Step 2 completed")
    return data

async def step3(data):
    data["step3"] = "done"
    print("STEPS : Step 3 completed")
    return data



"""
STEPS AFTER MARKET CLEARING
"""

async def step4_retrieve_market_clearing_info(data):
    # data["step4"] = "done"
    print('market clearing info: ', data.get("market_data"))
    print("STEPS : Step 4 completed - in market clearing")
    return data


STEP_MAP = {
    "market_open": [
    step1, 
    # time_tool_step, 
    # step2, 
    step_market_open, 
    step_retrieve_market_info, 
    step_fc_demand, 
    step_fc_solar, 
    step_fc_prices, 
    step_battery_utility_calculator, 
    step_publish_bid, 
    step3
    ], 
    "market_clearing":[
    step4_retrieve_market_clearing_info
    ],
    }
"""
Steps prepare bid: 
- retrieve the market and product information
- retrieve all the data forecasts
- compute the BUC
- prepare the bid 
- send the bid to the market
"""


#"reward_received": [step_process_reward,]
"""
Steps receive market results:
- save the market results in the database
"""



"""
Steps of the pipeline that should run in the background
"""

"""
PREPARATION PHASE

1. Start 3 days before the market opens (Thursday if market opens Sunday Noon)

2. Optional: talk with human -> change inputs for forecast energy use

3. Get forecasts
- weather
- solar generation
- energy use

- wholesale price
- community price
- eeg price
- grid price

4. Battery utility calculator: get the suggested bid

5. Check prosumer profile: send bid or discuss with human first
5a. Retrieve prosumer profile -> discuss with human

6. Optional: Adjust bid with new information

7. Optional: Adjust the bid with the risk score of the prosumer

8. Send bid to market at TIME = MARKET_OPENS


TO DO: LOG EVERY STAGE CLEARLY


"""
# TO DO: read from database
# start = datetime(2023, 1, 1, hour=13)
# end = datetime(2023, 1, 2, hour=13)  # One week

# # Probably remove when connected to database
# def load_first_column(csv_path):
#     df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
#     df.columns = df.columns.str.strip()  # remove extra spaces
#     first_col = df.columns[0]
#     return df[first_col].loc[start:end]

# prosumer_preference_check_bid = False


# Step Forecasts

# async def step_fc_demand(data):
#     print('STEPS : start step fc demand')
#     demand = load_first_column("data/example_data/demand.csv")
#     data["demand_fc"] = demand
#     print('STEPS : demand fc')
#     return data

# async def step_fc_solar_gen(data):
#     solar_gen = load_first_column("data/example_data/solar.csv")
#     data["solar_gen_fc"] = solar_gen
#     print('STEPS : solar gen fc')
#     return data

# async def step_fc_wholesale_price(data):
#     # With connection to database: extract from there
#     prices = pd.read_csv("data/example_data/prices.csv", index_col=0, parse_dates=True)
#     prices.columns = prices.columns.str.strip()

#     wholesale_price = prices["wholesale"].loc[start:end]
#     data["wholesale_price_fc"] = wholesale_price
#     print("STEPS : wholesale price fc")
#     return data

# async def step_fc_grid_price(data):
#     # With connection to database: extract from there
#     prices = pd.read_csv("data/example_data/prices.csv", index_col=0, parse_dates=True)
#     prices.columns = prices.columns.str.strip()

#     grid_price = prices["grid"].loc[start:end]
#     data["grid_price_fc"] = grid_price
#     print("STEPS : grid price fc")
#     return data

# async def step_fc_eeg_price(data):
#     # With connection to database: extract from there
#     prices = pd.read_csv("data/example_data/prices.csv", index_col=0, parse_dates=True)
#     prices.columns = prices.columns.str.strip()

#     eeg_price = prices["eeg"].loc[start:end]
#     data["eeg_price_fc"] = eeg_price
#     print("STEPS : eeg price fc")
#     return data

# async def step_fc_community_price(data):
#     # With connection to database: extract from there
#     prices = pd.read_csv("data/example_data/prices.csv", index_col=0, parse_dates=True)
#     prices.columns = prices.columns.str.strip()

#     community_price = prices["community"].loc[start:end]
#     data["community_price_fc"] = community_price
#     print("STEPS : community price fc")
#     return data



"""
Step BUC
"""



"""
The prosumer has a preference on whether they want to check the bid before sending it to the market;
Currently, we assume that they do not want this. The other option will be implemented at a later stage. 
"""
# async def step_prosumer_preference_check_bid(data):
#     if prosumer_preference_check_bid == True: 
#         # Do something
#         return data
#     else:
#         return data



# List of all steps in order
# STEPS = [step1, time_tool_step, step2, step3]
# STEPS = [
#     step_fc_demand, 
#     step_fc_solar_gen, 
#     step_fc_wholesale_price, 
#     step_fc_grid_price, 
#     step_fc_eeg_price, 
#     step_fc_community_price, 
#     step_battery_utility_calculator
#     ]
