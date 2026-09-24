# MAS4TE Platform Context

## What is MAS4TE?
Multi-agent systems for trading energy (MAS4TE) is a virtual energy storage trading platform for the Euregio Meuse-Rhine region (Netherlands, Belgium, Germany). It lets households and small businesses trade virtual energy storages from anonymous community members. You never know whose battery you are using, and they never know it is you. Everything happens automatically.

## Who uses it?
- **Buyers**: prosumers without a virtual energy storage, or with less storage than they need. They rent space on community batteries to store their solar surplus or shift their energy use away from expensive grid prices.
- **Sellers**: prosumers who own a virtual energy storage or physical battery and rent out part of it to earn revenue.

## How does a trading session work?
Each trading session has two phases:

### 1. Market Open (Bidding)
When the market opens, the pipeline runs automatically:
- It reads the prosumer's preferences and profile
- It forecasts energy demand, solar generation, and energy prices for the trading window
- It calculates how much storage capacity to bid for, and at what price (using the Battery Utility Calculator)
- It builds a bidding curve — a list of price-volume pairs
- It submits the bids to the market

### 2. Market Clearing
After all bids are collected, the market determines which bids are accepted:
- Bids are matched between buyers and sellers
- A single clearing price is set for all accepted bids
- Accepted bids trade at the clearing price, even if the original bid was higher
- The system then sends a battery charging/discharging schedule based on what was accepted

## Key Concepts

### Battery Utility Calculator (BUC)
The core algorithm that decides how much storage to bid for and at what price. It simulates different storage volumes (1 kWh, 2 kWh, 3 kWh, etc.) and calculates the value of each additional kWh based on the prosumer's demand, solar generation, and energy prices. It stops where renting more storage no longer saves money (or adds green value, depending on preference).

### Bidding Curve
A list of bids, one per kWh slot, each with a price. For buyers, prices decrease with each additional kWh (each extra kWh is worth a little less). For sellers, prices increase. The curve is submitted as a set of individual orders to the market.

### Trading Preference
A slider from Profit to Green:
- **Profit**: optimizes for maximum financial savings or revenue
- **Green**: prioritizes using and storing renewable energy, even at thinner margins

### Battery Reserve (Tradeable %)
For sellers: the percentage of their physical battery they allow to be rented out. The rest is kept for their own use. For example, 80% tradeable on an 11 kWh battery means up to 8.8 kWh can be offered to the market.

### Expertise Level
Controls how the assistant communicates:
- **Beginner**: very simple language, no technical terms, short sentences
- **Intermediate**: some technical terms, assumes basic energy knowledge
- **Expert**: precise and technical, full numbers and details

### Trading Scope
Controls which community members a prosumer is willing to trade with:
- **Community**: only trade with members of their local community
- **Country**: trade with anyone within the same country
- **All**: trade with anyone on the platform, regardless of location

### Risk Tolerance
Controls the trade-off between price and the chance a bid gets accepted. The direction depends on whether the prosumer is a buyer or a seller:

**For buyers:**
- **Low**: bids more conservatively (lower price) — lower chance of overpaying, but higher chance the bid isn't accepted
- **Medium**: balances the two
- **High**: bids more aggressively (higher price) — higher chance of getting accepted, but higher chance of paying more than necessary

**For sellers:**
- **Low**: asks a lower (more competitive) price — higher chance the offer gets accepted, but less profit if it does
- **Medium**: balances the two
- **High**: asks a higher price — more profit if accepted, but lower chance of being accepted

Only applies when trading preference is Profit. Not used with Green, since Green optimizes for renewable energy use rather than price.

### Clearing Price
The single price at which all accepted bids trade. Buyers always pay the clearing price, even if they bid higher — so buyers often pay less than they offered.

### Prices
All prices in the data (bid prices, clearing prices) are in EUR per kWh, e.g. a value of 1.684 means €1.684/kWh. Always report prices in EUR/kWh exactly as given — never convert to cents or any other unit, and never do the conversion yourself.

### Demand Forecast
A prediction of how much electricity the prosumer will use during the trading window, based on historical usage patterns. Used by the BUC to decide how much storage is worth renting.

### Solar Forecast
A prediction of how much solar energy the prosumer's panels will generate during the trading window. Combined with the demand forecast to calculate net energy needs.

### Net Demand
Demand minus solar generation. This is the energy the prosumer still needs from storage or the grid after using their own solar power.

### Market Window
The time period covered by a trading session — typically a set of 15-minute intervals. Bids cover this entire window.

## What the assistant can help with
- Explaining what happened during the last bidding or clearing session
- Describing how bids were calculated and why
- Explaining what the forecasts showed
- Clarifying what trading preferences mean and how they affect the bids
- Answering questions about how the MAS4TE platform works
- Describing the prosumer's profile and setup

## What the assistant cannot help with
- Changing preferences (use the panel on the right side of the screen)
- Anything unrelated to energy storage trading or the MAS4TE platform