"""
Agentic AI Base Module - Abstract base class for AI agents.

This module defines the core lifecycle pattern for all AI agents in the system:
    PLAN -> PERCEIVE -> REASON -> ACT

Library Dependencies:
    - abc: Python standard library for Abstract Base Classes (https://docs.python.org/3/library/abc.html)
    - datetime: Python standard library for date/time handling (https://docs.python.org/3/library/datetime.html)
    - json: Python standard library for JSON serialization (https://docs.python.org/3/library/json.html)
    - os: Python standard library for OS interaction (https://docs.python.org/3/library/os.html)
    - sys: Python standard library for system-specific functions (https://docs.python.org/3/library/sys.html)
"""

# abc.ABC: Abstract Base Class - prevents direct instantiation, requires subclass implementation
# abc.abstractmethod: Decorator marking methods that MUST be implemented by subclasses
# Reference: https://docs.python.org/3/library/abc.html
from abc import ABC, abstractmethod

# datetime: Core date/time class for timestamps
# timezone: UTC timezone constant for timezone-aware datetime objects
# Reference: https://docs.python.org/3/library/datetime.html
from datetime import datetime, timezone

# json: JSON encoder/decoder for serializing Python objects to JSON strings
# Reference: https://docs.python.org/3/library/json.html
import json

# os: Operating system interface for environment variables access
# Reference: https://docs.python.org/3/library/os.html
import os

# sys: System-specific parameters, provides access to stderr for debug output
# Reference: https://docs.python.org/3/library/sys.html
import sys


class AgenticAIBase(ABC):
    """
    Abstract base class defining the agentic AI lifecycle.

    Subclasses implement perceive/reason/act/plan to build
    domain-specific agents with tool-use capabilities.

    The lifecycle follows: PLAN -> PERCEIVE -> REASON -> ACT

    Attributes:
        _state (dict): Internal state dictionary tracking phase, data, reasoning, actions
        _tools (dict): Registry of callable tools available to the agent
    """

    def __init__(self):
        """
        Initialize the agent with empty state and tool registry.

        Creates the internal state dictionary with keys:
            - phase: Current lifecycle phase (initialized, planning, perceiving, reasoning, acting, completed)
            - data: Raw data gathered during perceive phase
            - reasoning: Analysis results from reason phase
            - actions: Actions taken/outputs generated during act phase
            - plan: List of planned steps
            - tool_log: Log of all tool invocations with timestamps
        """
        # Initialize agent state dictionary to track lifecycle phases and data
        # dict literal creates a new dictionary object
        # Reference: https://docs.python.org/3/library/stdtypes.html#dict
        self._state = {
            "phase": "initialized",      # Current lifecycle phase - str type
            "data": {},                  # Raw data from perceive - dict type
            "reasoning": {},             # Analysis from reason - dict type
            "actions": {},               # Outputs from act - dict type
            "plan": [],                  # Planned steps - list type
            "tool_log": [],              # Tool invocation history - list type
        }
        # Initialize empty tool registry dictionary
        # Tools are registered as {name: {"func": callable, "description": str}}
        self._tools = {}

    def register_tool(self, name: str, func: callable, description: str = ""):
        """
        Register a callable tool the agent can invoke by name.

        Args:
            name (str): Unique identifier for the tool
            func (callable): Python callable (function/method) to execute
            description (str): Human-readable description of tool purpose

        Example:
            agent.register_tool("fetch_data", self._fetch_data, "Fetches stock data")
        """
        # Store tool in registry dict with name as key
        # Value is a dict containing the callable function and its description
        # dict.__setitem__: https://docs.python.org/3/library/stdtypes.html#dict
        self._tools[name] = {"func": func, "description": description}

    def _is_debug(self) -> bool:
        """
        Check if debug mode is enabled via environment variable.

        Returns:
            bool: True if DEBUG env var is set to "true", "1", or "yes"

        Uses:
            os.getenv(): Retrieves environment variable value
            str.lower(): Converts string to lowercase for case-insensitive comparison
        """
        # os.getenv(key, default): Get environment variable or default value
        # Reference: https://docs.python.org/3/library/os.html#os.getenv
        # str.lower(): Convert to lowercase - https://docs.python.org/3/library/stdtypes.html#str.lower
        # tuple membership test with 'in' operator
        return os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

    def debug_log(self, label: str, data, agent_name: str = None):
        """
        Log data to stderr if DEBUG mode is enabled.

        Args:
            label (str): Description of the data being logged
            data: The data to log (will be JSON serialized if possible)
            agent_name (str, optional): Agent name (defaults to class name)

        Output Format:
            [DEBUG] [AgentName] Label:
            {json_formatted_data}
        """
        # Early return pattern - skip if debug disabled
        if not self._is_debug():
            return

        # Use provided agent_name or fall back to class name via __class__.__name__
        # self.__class__.__name__: Gets class name string
        # Reference: https://docs.python.org/3/reference/datamodel.html#special-attributes
        name = agent_name or self.__class__.__name__

        # print() with file=sys.stderr directs output to standard error stream
        # sys.stderr: Standard error stream for diagnostic output
        # Reference: https://docs.python.org/3/library/sys.html#sys.stderr
        print(f"\n[DEBUG] [{name}] {label}:", file=sys.stderr)

        try:
            # Try to serialize data as JSON for readable output
            # hasattr(): Check if object has named attribute
            # Reference: https://docs.python.org/3/library/functions.html#hasattr
            if hasattr(data, 'to_dict'):
                # pandas DataFrame.to_dict(): Convert DataFrame to dict
                # Reference: https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_dict.html
                output = data.to_dict()
            elif hasattr(data, 'model_dump'):
                # Pydantic BaseModel.model_dump(): Convert model to dict
                # Reference: https://docs.pydantic.dev/latest/api/base_model/#pydantic.BaseModel.model_dump
                output = data.model_dump()
            else:
                # Use data directly if no conversion method available
                output = data
            # json.dumps(): Serialize Python object to JSON string
            # indent=2: Pretty print with 2-space indentation
            # default=str: Use str() for non-serializable objects
            # Reference: https://docs.python.org/3/library/json.html#json.dumps
            print(json.dumps(output, indent=2, default=str), file=sys.stderr)
        except (TypeError, ValueError):
            # Fall back to repr() for non-serializable data
            # repr(): Return printable representation of object
            # Reference: https://docs.python.org/3/library/functions.html#repr
            print(repr(data), file=sys.stderr)

    def debug_log_no_data(self, source: str, reason: str, agent_name: str = None):
        """
        Log 'no data available' message if DEBUG mode is enabled.

        Args:
            source (str): The data source that returned no data
            reason (str): Why the data is not available
            agent_name (str, optional): Agent name (defaults to class name)
        """
        # Early return if debug mode is disabled
        if not self._is_debug():
            return

        # Get agent name from parameter or class name
        name = agent_name or self.__class__.__name__
        # Print formatted no-data message to stderr
        print(f"\n[DEBUG] [{name}] No data available from {source}: {reason}", file=sys.stderr)

    def use_tool(self, tool_name: str, **kwargs):
        """
        Invoke a registered tool and log the call.

        Args:
            tool_name (str): Name of the registered tool to invoke
            **kwargs: Keyword arguments to pass to the tool function

        Returns:
            Any: Result returned by the tool function

        Raises:
            ValueError: If tool_name is not registered

        Side Effects:
            - Logs tool invocation to _state["tool_log"]
        """
        # Check if tool exists in registry using 'in' membership test
        # dict.__contains__: https://docs.python.org/3/library/stdtypes.html#dict
        if tool_name not in self._tools:
            # raise: Python exception raising statement
            # ValueError: Exception for invalid argument values
            # Reference: https://docs.python.org/3/library/exceptions.html#ValueError
            raise ValueError(f"Tool '{tool_name}' is not registered.")

        # Invoke tool function with provided kwargs
        # **kwargs unpacking: https://docs.python.org/3/tutorial/controlflow.html#keyword-arguments
        result = self._tools[tool_name]["func"](**kwargs)

        # Log tool invocation with timestamp to tool_log
        # list.append(): Add item to end of list
        # Reference: https://docs.python.org/3/library/stdtypes.html#list
        self._state["tool_log"].append({
            "tool": tool_name,                              # Tool name string
            "kwargs": kwargs,                               # Arguments dict
            # datetime.now(timezone.utc): Get current UTC timestamp
            # .isoformat(): Convert to ISO 8601 string format
            # Reference: https://docs.python.org/3/library/datetime.html#datetime.datetime.isoformat
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return result

    @abstractmethod
    def perceive(self):
        """
        Gather data from the environment using registered tools.

        Abstract method - MUST be implemented by subclasses.
        This is the data collection phase of the lifecycle.

        Typical implementation:
            - Fetch external data (APIs, databases, files)
            - Store raw data in self._state["data"]
        """

    @abstractmethod
    def reason(self):
        """
        Analyze gathered data and produce insights.

        Abstract method - MUST be implemented by subclasses.
        This is the analysis phase of the lifecycle.

        Typical implementation:
            - Process data from self._state["data"]
            - Apply business logic, ML models, or heuristics
            - Store results in self._state["reasoning"]
        """

    @abstractmethod
    def act(self):
        """
        Decide on actions based on reasoning.

        Abstract method - MUST be implemented by subclasses.
        This is the action/output phase of the lifecycle.

        Typical implementation:
            - Generate final output based on reasoning
            - Store in self._state["actions"]
        """

    @abstractmethod
    def plan(self):
        """
        Create a step-by-step execution plan.

        Abstract method - MUST be implemented by subclasses.
        This is the planning phase of the lifecycle.

        Typical implementation:
            - Define ordered list of steps
            - Store in self._state["plan"]
        """

    def execute(self):
        """
        Orchestrate the full agentic lifecycle: plan -> perceive -> reason -> act.

        Executes each lifecycle phase in order:
            1. PLANNING: Define execution strategy
            2. PERCEIVING: Gather data from environment
            3. REASONING: Analyze data and generate insights
            4. ACTING: Produce final output/actions

        Returns:
            dict: Copy of final agent state via get_state()
        """
        # Phase 1: Planning
        # Update state phase tracker
        self._state["phase"] = "planning"
        # Call abstract plan() method implemented by subclass
        self.plan()

        # Phase 2: Perceiving
        self._state["phase"] = "perceiving"
        # Call abstract perceive() method implemented by subclass
        self.perceive()

        # Phase 3: Reasoning
        self._state["phase"] = "reasoning"
        # Call abstract reason() method implemented by subclass
        self.reason()

        # Phase 4: Acting
        self._state["phase"] = "acting"
        # Call abstract act() method implemented by subclass
        self.act()

        # Mark lifecycle as completed
        self._state["phase"] = "completed"
        # Return copy of final state
        return self.get_state()

    def get_state(self) -> dict:
        """
        Return a copy of the current agent state.

        Returns:
            dict: Shallow copy of _state dictionary

        Note:
            Returns a copy to prevent external modification of internal state
        """
        # dict(self._state): Create shallow copy of state dictionary
        # Reference: https://docs.python.org/3/library/stdtypes.html#dict
        return dict(self._state)

    def reset(self):
        """
        Clear state for re-execution.

        Resets all state fields to initial values, allowing
        the agent to be executed again with fresh state.
        """
        # Reinitialize state dictionary to default values
        self._state = {
            "phase": "initialized",    # Reset phase to initial state
            "data": {},                # Clear collected data
            "reasoning": {},           # Clear reasoning results
            "actions": {},             # Clear actions/outputs
            "plan": [],                # Clear execution plan
            "tool_log": [],            # Clear tool invocation history
        }
