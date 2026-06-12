from app.accounting.events import AccountingEvent


def is_reward_event(event: AccountingEvent) -> bool:
    return event.event_type == "EARN_REWARD"
