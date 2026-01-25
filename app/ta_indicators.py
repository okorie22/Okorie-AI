"""
Technical Analysis Indicators - Fallback Implementation
Simple fallback when pandas_ta is not available
"""

class TechnicalAnalysis:
    """Simple fallback technical analysis functions"""
    
    @staticmethod
    def sma(data, length=20):
        """Simple Moving Average"""
        if len(data) < length:
            return None
        return sum(data[-length:]) / length
    
    @staticmethod
    def ema(data, length=20):
        """Exponential Moving Average"""
        if len(data) < length:
            return None
        if len(data) == length:
            return sum(data) / length
        
        multiplier = 2 / (length + 1)
        ema_value = data[0]
        for price in data[1:]:
            ema_value = (price * multiplier) + (ema_value * (1 - multiplier))
        return ema_value
    
    @staticmethod
    def rsi(data, length=14):
        """Relative Strength Index"""
        if len(data) < length + 1:
            return None
        
        deltas = [data[i] - data[i-1] for i in range(1, len(data))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        avg_gain = sum(gains[-length:]) / length
        avg_loss = sum(losses[-length:]) / length
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    @staticmethod
    def macd(data, fast=12, slow=26, signal=9):
        """MACD (Moving Average Convergence Divergence) - Returns DataFrame"""
        import pandas as pd
        
        if isinstance(data, pd.Series):
            close = data
        else:
            close = pd.Series(data)
        
        if len(close) < slow:
            return pd.DataFrame()
        
        # Calculate EMAs using pandas ewm
        fast_ema = close.ewm(span=fast, adjust=False).mean()
        slow_ema = close.ewm(span=slow, adjust=False).mean()
        
        macd_line = fast_ema - slow_ema
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        
        # Return DataFrame in pandas_ta format
        result = pd.DataFrame({
            f'MACD_{fast}_{slow}_{signal}': macd_line,
            f'MACDh_{fast}_{slow}_{signal}': histogram,
            f'MACDs_{fast}_{slow}_{signal}': signal_line
        })
        
        return result
    
    @staticmethod
    def bbands(data, length=20, std=2):
        """Bollinger Bands - Returns DataFrame"""
        import pandas as pd
        
        if isinstance(data, pd.Series):
            close = data
        else:
            close = pd.Series(data)
        
        if len(close) < length:
            return pd.DataFrame()
        
        sma = close.rolling(window=length).mean()
        std_dev = close.rolling(window=length).std()
        
        upper = sma + (std_dev * std)
        mid = sma
        lower = sma - (std_dev * std)
        
        result = pd.DataFrame({
            f'BBL_{length}_{std}': lower,
            f'BBM_{length}_{std}': mid,
            f'BBU_{length}_{std}': upper
        })
        
        return result

# Create ta object for compatibility
ta = TechnicalAnalysis()
