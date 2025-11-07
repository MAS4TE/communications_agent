# market_adapter.py
import asyncio

class MarketAdapter:
    """
    MarketAdapter handles all communication with the market.
    Currently, functions are placeholders showing what will need to be implemented.
    """

    def __init__(self, market_to_llm_queue, llm_to_market_queue, agent_state, pipeline=None):
        # TODO: Initialize any API clients, authentication, or state here
        self.market_to_llm_queue = market_to_llm_queue
        self.llm_to_market_queue = llm_to_market_queue
        self.agent_state = agent_state
        self.pipeline = pipeline
        self.connected = False
        self._running = False
        # pass

    async def connect(self):
        """
        Connect to the market.
        TODO: Implement actual connection logic (API, MQTT, etc.)
        """
        await asyncio.sleep(0.1) # placeholder for async connection 
        self.connected = True 
        print("MarketAdapter connected")
        # pass

    async def disconnect(self):
        """
        Disconnect from the market.
        TODO: Cleanup resources, close connections
        """
        self._running = False
        await asyncio.sleep(0.1) # placeholder for clean disconnect
        self.connected = False
        print('MarketAdapter disconnected')
        # pass

    async def run(self):
        """
        Main loop of the MarketAdapter.
        """
        if not self.connected: 
            raise RuntimeError("MarketAdapter must be connected before running.") 
        self._running = True 
        await self.listen_to_market()

    async def listen_to_market(self):
        """
        Main loop listening for market events via the queue.
        """
        while self._running: 
            try: 
                message = await self.market_to_llm_queue.get() # wait for next market message 
                await self.handle_market_message(message) 
            except Exception as e: 
                print(f"Error handling market message: {e}") 
            await asyncio.sleep(0) # yield control to event loop

    async def handle_market_message(self, message) :   
        """
        Dispatch market events (e.g., market open, market clearing).
        TODO: Implement receiving logic.
        """
        msg_type = message.get("type")
        if msg_type == "market_opened":
            # get market information out of message
            await self.handle_market_open(message)
        elif msg_type == "market_cleared":
            await self.handle_market_clearing(message)
        else:
            print(f"Unknown market message type: {msg_type}")


    async def handle_market_open(self, message):
        """
        Handle a 'market opened' event, retrieve the current bid and send it to the market queue.
        TODO: Implement preparing and sending a bid
        """
        current_bid = self.agent_state.get_current_bid(message) # retrieve current bid from the agent state
        await self.llm_to_market_queue.put(current_bid)
        print(f"Submitted bid: {current_bid}")

        # pass
        # Note: ensure that bid has correct format for market
        # when this bid has been submitted, give message to pipeline with new market opening and closing times
        if self.pipeline: # TO DO: check whether this needs to happen here, or after market clearing
            begin = None # TO DO
            end = None # TO DO
            next_market_times = begin, end
            await self.pipeline.prepare_bid(next_market_times)

    async def handle_market_clearing(self, message):
        """
        Handle a 'market cleared' event.
        TODO: Implement storing results and updating history
        """
        # await agent_state.add_market_results(message)
        # TO DO: make a file or database table per market, as there will be multiple markets in future steps
        pass


