import asyncio

class Pipeline: 
    """
    Handles the logic for preparing the bid based on all avaiable information.
    TO DO: implement the coordination of tasks
    """

    def __init__(self, agent_state):
        self.agent_state = agent_state
        self._running = False

    async def start_pipeline(self):
        """Start the pipeline. """
        self._running = True
        print('pipeline started')

    async def stop_pipeline(self):
        """Stop the pipeline. """
        self._running = False
        print('pipeline stopped')

    async def prepare_bid(self):
        """Top-level method to run all preparation steps."""
        print("Preparing for the next market opening")
        await self.retrieve_prediction_models() # Do this for all necessary predictions
        await self.retrieve_prosumer_profile() # semi-static information
        await self.retrieve_prosumer_input() # additional information that human inputted in chat
        await self.update_predictions() #Adjust the forecasts by using the prosumer_input
        await self.run_battery_utility_calculator() # Use the BUC to calculate the bid based on the predictions
        await self.set_current_bid() # Save the BUC bid

        # Possibly: Discuss the bid with the prosumer; if changed -> set_current_bid
        # See where to put this, as this may come from the chat interface-part fully
        # await self.discuss_with_prosumer() # Update the bid if the human has asked for it explicitly

    async def retrieve_prediction_models(self):
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
        pass

    async def retrieve_prosumer_profile(self):
        """Retrieve static prosumer profile from agent state. """
        prosumer_profile = self.agent_state.get_prosumer_profile()
        return prosumer_profile
    
    async def retrieve_prosumer_input(self):
        """Retrieve variable prosumer input from chat interaction. """
        pass

    async def update_predictions(self):
        """
        Update predictions if necessary.
        Use the retrieved prosumer input to update the forecasting for the BUC
        This needs an LLM to go from natural language to changing the time-series of the prediction
        """
        pass

    async def run_battery_utility_calculator(self):
        """
        Use the forecast (with or without changes by update_predictions) as input for the BUC
        """
        pass

    async def set_current_bid(self): 
        """
        Update the current bid in the agent state based on the output of the BUC
        """
        #self.agent_state.set_current_bid()
