"""Root API endpoints."""

from pathlib import Path
import os
from fastapi import APIRouter
from fastapi.responses import FileResponse
from fastapi import Request

router = APIRouter()


def create_bids(
    product_tuples,
) -> list[dict]:
    # TODO OU
    # make this more than a placeholder function
    # use battery utility calculator and LLM

    return [
        {
            "start_time": product_tuples[0],
            "end_time": product_tuples[1],
            "volume": 0,
            "price": 0,
            "c_rate": 1,
        }
    ]


@router.get("/", response_class=FileResponse)
def index():
    # Get the path to the static directory relative to this file
    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
    return Path(static_dir) / "index.html"


@router.get("/get_queue")
def some_router_function(request: Request):
    if request.app.state.market_to_llm_queue is None:
        return {200, "No queue"}

    market_message = request.app.state.market_to_llm_queue.get()

    if market_message["msg"] == "calculate bids":
        bids = create_bids(product_tuples=market_message["product_tuples"])
        print(f"LLM Bids: {bids}")
        request.app.state.llm_to_market_queue.put(
            {"msg": "calculated bids", "bids": bids}
        )
    elif market_message["msg"] == "market result":
        # feed_to_llm()
        print("Feeding to LLM")

    return 200
