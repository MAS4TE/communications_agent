
class FooService:
    
    def echo_test(self, value: int = 1):
        """Returns the received argument for debugging."""
        return {"received_value": value}


class BarService:

    def multi_argument_test(self, value: int, factor: float = 1.0):
        """
        Returns a dictionary with the received value and a computed result.

        Args:
            value (int): The main input value.
            factor (float, optional): A multiplier for the value. Defaults to 1.0.

        Returns:
            dict: Contains the original value, factor, and a computed result.
        """
        return {
            "received_value": value,
            "factor": factor,
            "computed": value * factor
        }
