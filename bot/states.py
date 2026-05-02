"""FSM (ТЗ v2)."""

from aiogram.fsm.state import State, StatesGroup


class EstimationStates(StatesGroup):
    waiting_for_input = State()
    parsing = State()
    confirming_position = State()
    manual_price_entry = State()
    editing_quantity = State()
    adding_position_name = State()
    adding_position_qty = State()
    adding_position_price = State()
    entering_object_name = State()
    entering_client_name = State()
    entering_contact_name = State()
    final_review = State()


class AdminImportStates(StatesGroup):
    waiting_file = State()
    confirming_import = State()
