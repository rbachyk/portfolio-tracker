from app.binance import endpoints

REQUEST_WEIGHTS = {
    endpoints.ACCOUNT_INFO: 20,
    endpoints.DEPOSIT_HISTORY: 1,
    endpoints.EXCHANGE_INFO: 20,
    endpoints.EARN_FLEXIBLE_POSITIONS: 150,
    endpoints.EARN_FLEXIBLE_REDEMPTIONS: 150,
    endpoints.EARN_FLEXIBLE_REWARDS: 150,
    endpoints.EARN_FLEXIBLE_SUBSCRIPTIONS: 150,
    endpoints.EARN_LOCKED_POSITIONS: 150,
    endpoints.EARN_LOCKED_REDEMPTIONS: 150,
    endpoints.EARN_LOCKED_REWARDS: 150,
    endpoints.EARN_LOCKED_SUBSCRIPTIONS: 150,
    endpoints.MY_TRADES: 20,
    endpoints.TICKER_PRICE: 4,
    endpoints.WITHDRAW_HISTORY: 18000,
}
