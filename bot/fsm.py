from aiogram.fsm.state import State, StatesGroup


class StartMonitoringForm(StatesGroup):
    """States for creating a new monitoring task."""

    url = State()
    districts = State()  # Optional: select allowed districts
    name = State()


class StopMonitoringForm(StatesGroup):
    """States for stopping an existing monitoring task."""

    choosing = State()


class StatusForm(StatesGroup):
    """States for viewing monitoring status."""

    choosing = State()
