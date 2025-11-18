import asyncio
import pandas as pd
from communication_agent.services.battery_utility_calculator import BatteryUtilityCalculator


class Pipeline: 
    """
    Handles the logic for preparing the bid based on all available information.
    TO DO: implement the coordination of tasks
    """

    def __init__(self, agent_state):
        self.agent_state = agent_state
        self._running = False

    def start_pipeline(self):
    # async def start_pipeline(self):
        """Start the pipeline. """
        self._running = True
        print('pipeline started')

    def stop_pipeline(self):
        """Stop the pipeline. """
        self._running = False
        print('pipeline stopped')

    def prepare_bid(self):
        """Top-level method to run all preparation steps."""
        print("Preparing for the next market opening")
        # at some point, probably save the predictions somewhere, probably in agent state? 
        # self.retrieve_prediction_models() # Retrieve predictions in buc
        self.retrieve_prosumer_profile() # semi-static information
        self.retrieve_prosumer_input() # additional information that human inputted in chat
        self.update_predictions() #Adjust the forecasts by using the prosumer_input
        # self.run_battery_utility_calculator() # Use the BUC to calculate the bid based on the predictions
        self.set_buc_bid() # Save the BUC bid

        # Possibly: Discuss the bid with the prosumer; if changed -> set_current_bid
        # See where to put this, as this may come from the chat interface-part fully
        # await self.discuss_with_prosumer() # Update the bid if the human has asked for it explicitly

    def retrieve_prediction_models(self):
        """
        Add the different prediction models
        Communicate with databases (the assume one for now) and external services (maybe throough agent_state?)
        BUC needs
        1. demand
        2. solar generation
        3. grid prices
        4. eeg prices
        5. community prices
        6. wholesale prices
        Communicate here or through agent_state with the database 

        battery? 
        """
        print('in retrieve prediction function')
        # Extract the next market open and end time from the agent state 
        start_time_next_market = self.agent_state.upcoming_market["delivery_window"]["start"]
        end_time_next_market = self.agent_state.upcoming_market["delivery_window"]["end"]

        # Helper: load first column from CSV
        def load_first_column(csv_path):
            df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
            df.columns = df.columns.str.strip()  # remove extra spaces
            first_col = df.columns[0]
            return df[first_col].loc[start_time_next_market:end_time_next_market]

        # -----------------------------
        # Load data -> test data with perfect foresight as first test -> change by database prediction
        # -----------------------------
        demand = load_first_column("data/example_data/demand.csv")
        solar_gen = load_first_column("data/example_data/solar.csv")

        prices = pd.read_csv("data/example_data/prices.csv", index_col=0, parse_dates=True)
        prices.columns = prices.columns.str.strip()

        grid_price = prices["grid"].loc[start_time_next_market:end_time_next_market]
        eeg_price = prices["eeg"].loc[start_time_next_market:end_time_next_market]
        community_price = prices["community"].loc[start_time_next_market:end_time_next_market]
        wholesale_price = prices["wholesale"].loc[start_time_next_market:end_time_next_market]

        # print('demand ', demand)
        # print('solar gen ', solar_gen)
        # print('grid_price ', grid_price)

        return demand, solar_gen, grid_price, eeg_price, community_price, wholesale_price

    def retrieve_prosumer_profile(self):
        """Retrieve static prosumer profile from agent state. """
        prosumer_profile = self.agent_state.get_prosumer_profile()
        print('retrieve prosumer profile - empty')
        return prosumer_profile
    
    def retrieve_prosumer_input(self):
        """Retrieve variable prosumer input from chat interaction. """
        print('retrieve prosumer input - empty ')
        pass

    def update_predictions(self):
        """
        Update predictions if necessary.
        Use the retrieved prosumer input to update the forecasting for the BUC
        This needs an LLM to go from natural language to changing the time-series of the prediction
        """
        print('update predictions - empty')
        pass

    def run_battery_utility_calculator(self):
        """
        Use the forecast (with or without changes by update_predictions) as input for the BUC
        """
        print('In run_battery_utility_calculator')
        demand, solar_gen, grid_price, eeg_price, community_price, wholesale_price = self.retrieve_prediction_models()
        storage_size = self.agent_state.available_storage_capacity
        print('total storage size ', storage_size)
        # print(stop_here)
        buc = BatteryUtilityCalculator()
        print(f"\nCalculating utility for {storage_size} kWh battery...")

        try:
            # call calculate with series in positional order
            result = buc.calculate(
                storage_size,
                demand,
                solar_gen,
                grid_price,
                eeg_price,
                community_price,
                wholesale_price
            )

            print("\n" + "="*60)
            print("RESULTS")
            print("="*60)
            print(f"Storage size: {result['storage_size_kwh']} kWh")
            print(f"Baseline cost: ${result['baseline_cost']:.2f}")
            print(f"Optimized cost: ${result['optimized_cost']:.2f}")
            print(f"Cost savings: ${result['cost_savings']:.2f}")
            print("\nBidding curve:")
            print(result['bidding_curve'])

        except Exception as e:
            print(f"\nError: {e}")
            import traceback
            traceback.print_exc()
        return storage_size, result['baseline_cost']

    def set_buc_bid(self): 
        """
        Update the current bid in the agent state based on the output of the BUC
        """
        print('set the new bid from the BUC')
        storage_size, price = self.run_battery_utility_calculator()
        self.agent_state.set_current_bid(storage_size, price)
