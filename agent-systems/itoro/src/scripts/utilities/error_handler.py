"""
🌙 Anarcho Capital's Standardized Error Handler
Consistent error handling patterns across all trading system components
Built with love by Anarcho Capital 🚀
"""

import sys
import traceback
from typing import Optional, Dict, Any, Callable, Type, Union, NamedTuple
from enum import Enum
from src.scripts.shared_services.logger import debug, info, warning, error, critical

class ErrorResult(NamedTuple):
    """Structured error result with success flag and error details"""
    success: bool
    result: Any = None
    error_message: str = None
    error_category: str = None
    retry_possible: bool = False

class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class ErrorCategory(Enum):
    """Error categories for better handling"""
    TRADING = "TRADING"
    NETWORK = "NETWORK"
    DATA = "DATA"
    VALIDATION = "VALIDATION"
    CONFIGURATION = "CONFIGURATION"
    SYSTEM = "SYSTEM"

class TradingError(Exception):
    """Base exception for trading system errors"""
    def __init__(self, message: str, category: ErrorCategory, severity: ErrorSeverity, 
                 context: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.category = category
        self.severity = severity
        self.context = context or {}

class TradingExecutionError(TradingError):
    """Error during trade execution"""
    def __init__(self, message: str, token_address: str = None, amount: float = None, **kwargs):
        context = {'token_address': token_address, 'amount': amount}
        super().__init__(message, ErrorCategory.TRADING, ErrorSeverity.HIGH, context)

class NetworkTimeoutError(TradingError):
    """Network timeout error"""
    def __init__(self, message: str, timeout_seconds: float = None, **kwargs):
        context = {'timeout_seconds': timeout_seconds}
        super().__init__(message, ErrorCategory.NETWORK, ErrorSeverity.MEDIUM, context)

class DataValidationError(TradingError):
    """Data validation error"""
    def __init__(self, message: str, data_type: str = None, **kwargs):
        context = {'data_type': data_type}
        super().__init__(message, ErrorCategory.VALIDATION, ErrorSeverity.MEDIUM, context)

class ConfigurationError(TradingError):
    """Configuration error"""
    def __init__(self, message: str, parameter: str = None, **kwargs):
        context = {'parameter': parameter}
        super().__init__(message, ErrorCategory.CONFIGURATION, ErrorSeverity.HIGH, context)

class StandardErrorHandler:
    """Standardized error handler for consistent error management"""
    
    def __init__(self):
        self.error_counts: Dict[str, int] = {}
        self.error_handlers: Dict[Type[Exception], Callable] = {}
        self.recovery_strategies: Dict[ErrorCategory, Callable] = {}
        
        # Default recovery strategies
        self._setup_default_recovery_strategies()
    
    def _setup_default_recovery_strategies(self):
        """Setup default recovery strategies for different error categories"""
        
        def trading_recovery(error: TradingError) -> bool:
            """Recovery strategy for trading errors"""
            if error.severity == ErrorSeverity.CRITICAL:
                critical(f"Critical trading error: {str(error)}")
                return False  # Don't attempt recovery for critical errors
            
            warning(f"Trading error occurred, implementing recovery: {str(error)}")
            # Could implement retry logic, position checks, etc.
            return True
        
        def network_recovery(error: TradingError) -> bool:
            """Recovery strategy for network errors"""
            warning(f"Network error, will retry: {str(error)}")
            # Could implement exponential backoff, alternative endpoints, etc.
            return True
        
        def data_recovery(error: TradingError) -> bool:
            """Recovery strategy for data errors"""
            warning(f"Data error, using fallback: {str(error)}")
            # Could implement cache fallback, alternative data sources, etc.
            return True
        
        self.recovery_strategies = {
            ErrorCategory.TRADING: trading_recovery,
            ErrorCategory.NETWORK: network_recovery,
            ErrorCategory.DATA: data_recovery,
        }
    
    def handle_error(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Handle an error with standardized logging and recovery
        
        Returns:
            True if error was handled and system can continue
            False if error is critical and system should stop
        """
        error_type = type(error).__name__
        self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
        
        # Convert to TradingError if not already
        if not isinstance(error, TradingError):
            trading_error = self._convert_to_trading_error(error, context)
        else:
            trading_error = error
        
        # Log the error appropriately
        self._log_error(trading_error)
        
        # Attempt recovery
        return self._attempt_recovery(trading_error)
    
    def _convert_to_trading_error(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> TradingError:
        """Convert generic exception to TradingError"""
        message = str(error)
        
        # Categorize based on error type or message
        if isinstance(error, (ConnectionError, TimeoutError)):
            return NetworkTimeoutError(message, context=context)
        elif isinstance(error, ValueError):
            return DataValidationError(message, context=context)
        elif 'config' in message.lower():
            return ConfigurationError(message, context=context)
        else:
            return TradingError(message, ErrorCategory.SYSTEM, ErrorSeverity.MEDIUM, context)
    
    def _log_error(self, trading_error: TradingError):
        """Log error with appropriate severity"""
        message = f"[{trading_error.category.value}] {str(trading_error)}"
        
        if trading_error.context:
            context_str = ", ".join([f"{k}={v}" for k, v in trading_error.context.items()])
            message += f" (Context: {context_str})"
        
        if trading_error.severity == ErrorSeverity.CRITICAL:
            critical(message)
        elif trading_error.severity == ErrorSeverity.HIGH:
            error(message)
        elif trading_error.severity == ErrorSeverity.MEDIUM:
            warning(message)
        else:
            info(message)
    
    def _attempt_recovery(self, trading_error: TradingError) -> bool:
        """Attempt to recover from the error"""
        try:
            if trading_error.category in self.recovery_strategies:
                recovery_func = self.recovery_strategies[trading_error.category]
                return recovery_func(trading_error)
            else:
                # No specific recovery strategy, log and continue
                debug(f"No recovery strategy for {trading_error.category.value}, continuing")
                return True
                
        except Exception as recovery_error:
            error(f"Error during recovery attempt: {str(recovery_error)}")
            return False
    
    def safe_execute(self, func: Callable, *args, fallback_result=None, 
                    error_context: Optional[Dict[str, Any]] = None, 
                    return_error_result: bool = False, **kwargs) -> Union[Any, ErrorResult]:
        """
        Safely execute a function with standardized error handling
        
        Args:
            func: Function to execute
            *args: Function arguments
            fallback_result: Result to return on error (if return_error_result=False)
            error_context: Additional error context
            return_error_result: If True, return ErrorResult object instead of fallback
            **kwargs: Function keyword arguments
        
        Returns:
            Function result on success, fallback_result or ErrorResult on error
        """
        try:
            result = func(*args, **kwargs)
            if return_error_result:
                return ErrorResult(success=True, result=result)
            return result
        except Exception as e:
            trading_error = self._convert_to_trading_error(e, error_context)
            handled = self.handle_error(e, error_context)
            
            if return_error_result:
                return ErrorResult(
                    success=False,
                    result=fallback_result,
                    error_message=str(trading_error),
                    error_category=trading_error.category.value,
                    retry_possible=handled and trading_error.severity != ErrorSeverity.CRITICAL
                )
            
            if not handled:
                # Critical error, re-raise
                raise
            return fallback_result
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error handling statistics"""
        total_errors = sum(self.error_counts.values())
        
        return {
            'total_errors': total_errors,
            'error_counts': self.error_counts.copy(),
            'most_common_error': max(self.error_counts.items(), key=lambda x: x[1])[0] if self.error_counts else None
        }

# Global instance
_standard_error_handler = StandardErrorHandler()

def handle_error(error: Exception, context: Optional[Dict[str, Any]] = None) -> bool:
    """Global error handling function"""
    return _standard_error_handler.handle_error(error, context)

def safe_execute(func: Callable, *args, fallback_result=None, 
                error_context: Optional[Dict[str, Any]] = None, 
                return_error_result: bool = False, **kwargs) -> Union[Any, ErrorResult]:
    """Global safe execution function with enhanced error handling"""
    return _standard_error_handler.safe_execute(func, *args, fallback_result=fallback_result, 
                                               error_context=error_context,
                                               return_error_result=return_error_result, **kwargs)

def trading_operation(func: Callable):
    """Decorator for trading operations with standardized error handling"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            context = {
                'function': func.__name__,
                'args_count': len(args),
                'kwargs_keys': list(kwargs.keys())
            }
            
            handled = handle_error(e, context)
            if not handled:
                raise
            return None
    
    return wrapper

def network_operation(timeout_seconds: float = 30):
    """Decorator for network operations with timeout handling"""
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if 'timeout' in str(e).lower():
                    network_error = NetworkTimeoutError(
                        f"Network timeout in {func.__name__}: {str(e)}",
                        timeout_seconds=timeout_seconds
                    )
                    handled = handle_error(network_error)
                    if not handled:
                        raise
                    return None
                else:
                    # Re-raise other exceptions
                    raise
        
        return wrapper
    return decorator

def get_error_handler() -> StandardErrorHandler:
    """Get the global error handler instance"""
    return _standard_error_handler 