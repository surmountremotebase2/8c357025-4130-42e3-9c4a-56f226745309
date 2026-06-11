from surmount.base_class import Strategy, TargetAllocation
from surmount.technical_indicators import RSI
from surmount.logging import log

class TradingStrategy(Strategy):
    """
    Rolling Momentum Shifter

    Daily rebalance logic:
      - If RSI(HIBL, 10) > 78: go 100% UVXY (volatility hedge)
      - Else: rank 20 candidate ETFs by 33-day moving-average-return,
              allocate equally to top 4
    """

    def __init__(self):
        self.candidates = [
            "TQQQ", "UDOW", "HIBL", "ETHU", "BITX",
            "JNUG", "GDXU", "FBL",  "TECL", "FAS",
            "LABU", "SOXL", "TNA",  "UVIX", "WTID",
            "INTW", "NFLU", "SHY",  "BEEM", "UMDD",
        ]
        self.hedge = "UVXY"
        self.window = 33  # moving-average-return lookback (in daily returns)

    @property
    def interval(self):
        return "1day"

    @property
    def assets(self):
        return self.candidates + [self.hedge]

    @property
    def data(self):
        return []

    @staticmethod
    def _moving_average_return(ohlcv, ticker, window):
        """Mean of the last `window` daily returns for `ticker`.

        Matches Composer's moving-average-return: average of
        (close[i] - close[i-1]) / close[i-1] over the lookback.
        Returns None if there isn't enough clean data.
        """
        # Build the close series for this ticker across all bars
        closes = []
        for bar in ohlcv:
            try:
                closes.append(bar[ticker]["close"])
            except (KeyError, TypeError):
                # ticker missing on this bar → can't form a continuous series
                return None

        if len(closes) < window + 1:
            return None

        # Daily returns over the last `window` periods (needs window+1 closes)
        recent = closes[-(window + 1):]
        returns = []
        for prev, cur in zip(recent, recent[1:]):
            if prev == 0:
                return None
            returns.append((cur - prev) / prev)

        return sum(returns) / len(returns)

    def run(self, data):
        ohlcv = data.get("ohlcv")

        # Need 34 bars: 33 daily returns require 34 closes
        if not ohlcv or len(ohlcv) < self.window + 1:
            return TargetAllocation({})

        # --- Condition: RSI(HIBL, 10) > 78 → hedge with UVXY ---
        hibl_rsi = RSI("HIBL", ohlcv, 10)
        if hibl_rsi and hibl_rsi[-1] > 78:
            log(f"HIBL RSI={hibl_rsi[-1]:.1f} > 78 → allocating 100% UVXY")
            return TargetAllocation({self.hedge: 1.0})

        # --- Else: rank by 33-day moving-average-return ---
        # Composer moving-average-return = mean of the last N daily returns,
        # where daily return = (close[i] - close[i-1]) / close[i-1]
        scores = {}
        for ticker in self.candidates:
            mar = self._moving_average_return(ohlcv, ticker, self.window)
            if mar is not None:
                scores[ticker] = mar

        if not scores:
            return TargetAllocation({})

        top4 = sorted(scores, key=lambda t: scores[t], reverse=True)[:4]
        weight = round(1.0 / len(top4), 4)

        log(f"Top 4 by MA-return: {top4} | scores: {[round(scores[t], 4) for t in top4]}")
        return TargetAllocation({ticker: weight for ticker in top4})