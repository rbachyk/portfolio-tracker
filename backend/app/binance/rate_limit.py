from app.binance import endpoints

REQUEST_WEIGHTS = {
    endpoints.ACCOUNT_INFO: 20,
    endpoints.EXCHANGE_INFO: 20,
    endpoints.MY_TRADES: 20,
    endpoints.TICKER_PRICE: 4,
}
