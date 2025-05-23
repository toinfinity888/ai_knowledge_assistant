from enum import Enum

class ResponseStatus(str, Enum):
    OK = 'OK'
    NO_RESPONSE = 'NO RESPONSE'
    TIMEOUT = 'TIMEOUT'
    ERROR = 'ERROR'
    EMPTY_CONTEXT = 'EMPTY_CONTEXT'
    INVALID_INPUT = 'INVALID_INPUT'
    RATE_LIMITED = 'RATE_LIMITED'
    MODEL_OVERLOADED = 'MODEL_OVERLOADED'
    