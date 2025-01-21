from pydantic import BaseModel
import copy


class State(BaseModel):
    """The state is a representation of the system being tested.

    In other words, the state should capture the response of any
    pentesting action/operation, in a way that the resulting data
    (which represents the state itself) can be used to
    understand the current state of the system being tested.

    The state is both produced and consumed by the LLM.

    Implementations of the state should inherit from this class.
    """

    def copy(self):
        return copy.deepcopy(self)
